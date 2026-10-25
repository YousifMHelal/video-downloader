"""Download engine. No printing, no prompting, no Tk — usable from any front end.

The engine owns a single worker thread that drains a job queue. State lives on
mutable `Job` records; every change is announced through one `emit(event, payload)`
callback, which is always invoked from the worker thread. Front ends are expected
to marshal those events onto their own loop.
"""

from __future__ import annotations

import itertools
import os
import re
import shutil
import sys
import threading
import time
import urllib.request
import zipfile
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled

APP_NAME = "VideoDownloader"


def _data_root() -> Path:
    """Where ffmpeg, settings and history live.

    In a source checkout everything stays next to the code. A packaged build
    cannot write into its own bundle (and may sit in Program Files), so it uses
    the user's local app data instead.
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        root = Path(base) / APP_NAME
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _data_root()
FFMPEG_DIR = PROJECT_ROOT / "ffmpeg" / "bin"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# yt-dlp needs a JS runtime for some extractors; offer every one it supports.
JS_RUNTIMES = {"deno": {}, "node": {}, "bun": {}, "quickjs": {}}

INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*]')


# ── Options exposed to the UI ───────────────────────────────────────────────
@dataclass(frozen=True)
class Quality:
    id: str
    label: str
    hint: str
    selector: str
    audio_only: bool = False


QUALITIES: tuple[Quality, ...] = (
    Quality("1080", "1080p", "Full HD",
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
    Quality("720", "720p", "HD",
            "bestvideo[height<=720]+bestaudio/best[height<=720]"),
    Quality("480", "480p", "Data saver",
            "bestvideo[height<=480]+bestaudio/best[height<=480]"),
    Quality("best", "Best available", "Highest the source offers",
            "bestvideo+bestaudio/best"),
    Quality("audio", "Audio only", "MP3 at 192 kbps",
            "bestaudio/best", audio_only=True),
)
QUALITY_BY_ID = {q.id: q for q in QUALITIES}
QUALITY_LABELS = [q.label for q in QUALITIES]
QUALITY_BY_LABEL = {q.label: q for q in QUALITIES}

CONTAINERS = ("mp4", "mkv", "webm")
CONTAINER_LABELS = ("MP4", "MKV", "WebM")


class Status(str, Enum):
    QUEUED = "queued"
    PROBING = "reading link"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_final(self) -> bool:
        return self in (Status.DONE, Status.FAILED, Status.CANCELLED)


_ids = itertools.count(1)


@dataclass
class Job:
    url: str
    quality_id: str
    container: str
    output_dir: str
    id: str = field(default_factory=lambda: f"job{next(_ids):04d}")
    title: str = ""
    status: Status = Status.QUEUED
    is_playlist: bool = False
    item_index: int = 0
    item_count: int = 0
    percent: float = 0.0
    speed: float = 0.0
    eta: int = 0
    downloaded: int = 0
    total: int = 0
    current_file: str = ""
    message: str = ""
    dest_dir: str = ""
    queued_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def quality(self) -> Quality:
        return QUALITY_BY_ID.get(self.quality_id, QUALITIES[0])

    @property
    def display_title(self) -> str:
        return self.title or short_url(self.url)

    @property
    def recipe(self) -> str:
        q = self.quality
        return q.label if q.audio_only else f"{q.label} · {self.container.upper()}"


# ── Small helpers ───────────────────────────────────────────────────────────
def sanitize_name(name: str) -> str:
    """Strip characters Windows rejects in a file or folder name."""
    return INVALID_NAME_CHARS.sub("", name).strip() or "download"


def short_url(url: str, limit: int = 58) -> str:
    trimmed = re.sub(r"^https?://(www\.)?", "", url.strip())
    return trimmed if len(trimmed) <= limit else trimmed[: limit - 1] + "…"


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit in ("B", "KB") else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def human_speed(bytes_per_sec: float) -> str:
    if not bytes_per_sec:
        return "--"
    return f"{bytes_per_sec / 1024 / 1024:.1f} MB/s"


def human_eta(seconds: float) -> str:
    if not seconds:
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"0:{seconds:02d}"
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def looks_like_url(text: str) -> bool:
    return bool(re.match(r"^(https?://|www\.)\S+\.\S+", text.strip(), re.I))


def default_download_dir() -> str:
    home = Path(os.path.expanduser("~")) / "Downloads"
    return str(home if home.exists() else PROJECT_ROOT / "Downloads")


# ── ffmpeg bootstrap ────────────────────────────────────────────────────────
def ffmpeg_present() -> bool:
    return (FFMPEG_DIR / "ffmpeg.exe").exists() or shutil.which("ffmpeg") is not None


def ensure_ffmpeg(on_status: Callable[[str, float], None] | None = None) -> str:
    """Return a directory containing ffmpeg, downloading a build if needed.

    `on_status(message, percent)` reports the bootstrap download; percent is -1
    while the step has no measurable progress.
    """
    def report(message: str, percent: float = -1.0) -> None:
        if on_status:
            on_status(message, percent)

    exe = FFMPEG_DIR / "ffmpeg.exe"
    if exe.exists():
        return str(FFMPEG_DIR)

    system = shutil.which("ffmpeg")
    if system:
        report("Using ffmpeg from PATH")
        return str(Path(system).parent)

    report("Downloading ffmpeg…", 0.0)
    zip_path = PROJECT_ROOT / "ffmpeg.zip"
    temp_dir = PROJECT_ROOT / "ffmpeg_temp"

    def hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            fraction = min(1.0, block_num * block_size / total_size)
            report(f"Downloading ffmpeg… {fraction * 100:.0f}%", fraction)

    try:
        urllib.request.urlretrieve(FFMPEG_URL, zip_path, reporthook=hook)
        report("Extracting ffmpeg…", -1.0)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_dir)

        bin_src = next(p / "bin" for p in temp_dir.iterdir() if (p / "bin").is_dir())
        FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
        for item in bin_src.iterdir():
            shutil.move(str(item), str(FFMPEG_DIR / item.name))
        report("ffmpeg ready")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        zip_path.unlink(missing_ok=True)

    return str(FFMPEG_DIR)


# ── yt-dlp plumbing ─────────────────────────────────────────────────────────
class _Logger:
    """Routes yt-dlp chatter to a line sink instead of stdout."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        self._sink = sink

    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            self._sink(msg)

    def info(self, msg: str) -> None:
        self._sink(msg)

    def warning(self, msg: str) -> None:
        self._sink(msg)

    def error(self, msg: str) -> None:
        self._sink(msg)


def probe(url: str) -> tuple[str, bool, int]:
    """Return (title, is_playlist, item_count) without downloading."""
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "js_runtimes": JS_RUNTIMES,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}

    raw_title = info.get("title") or info.get("id") or ""
    title = sanitize_name(raw_title) if raw_title else ""
    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        return title or "Playlist", True, len(entries)
    return title, False, 1


def resolve_destination(job: Job, folder_name: str | None) -> str:
    base = job.output_dir or str(PROJECT_ROOT / "Downloads")
    dest = os.path.join(base, folder_name) if folder_name else base
    os.makedirs(dest, exist_ok=True)
    return dest


def build_options(job: Job, dest_dir: str, ffmpeg_path: str,
                  progress_hook: Callable[[dict], None],
                  log_sink: Callable[[str], None]) -> dict:
    quality = job.quality
    if job.is_playlist:
        pad = max(2, len(str(job.item_count)))
        stem = f"%(playlist_index)0{pad}d. %(title)s"
    else:
        stem = "%(title)s"

    opts: dict = {
        "format": quality.selector,
        "outtmpl": os.path.join(dest_dir, f"{stem}.%(ext)s"),
        "ffmpeg_location": ffmpeg_path,
        "progress_hooks": [progress_hook],
        "logger": _Logger(log_sink),
        "noprogress": True,
        "no_color": True,
        "noplaylist": False,
        "ignoreerrors": True,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "js_runtimes": JS_RUNTIMES,
    }

    if quality.audio_only:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
             "preferredquality": "192"},
            {"key": "FFmpegMetadata", "add_metadata": True},
        ]
    else:
        opts["merge_output_format"] = job.container
        opts["postprocessors"] = [{"key": "FFmpegMetadata", "add_metadata": True}]

    return opts


# ── Engine ──────────────────────────────────────────────────────────────────
Emit = Callable[[str, object], None]


class Engine:
    """Serial download worker.

    Events emitted: ``job`` (a Job changed), ``log`` ((job_id, line)),
    ``ffmpeg`` ((message, percent)), ``idle`` (queue drained).
    """

    def __init__(self, emit: Emit) -> None:
        self._emit = emit
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._pending: deque[str] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._cancel = threading.Event()
        self._shutdown = False
        self._current: str | None = None
        self._ffmpeg_path: str | None = None
        self._thread = threading.Thread(target=self._run, name="downloader",
                                        daemon=True)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._shutdown = True
        self._cancel.set()
        self._wake.set()

    # -- queue operations --------------------------------------------------
    def submit(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._pending.append(job.id)
        self._emit("job", job)
        self._wake.set()
        return job

    def jobs(self) -> list[Job]:
        with self._lock:
            return [self._jobs[i] for i in self._order if i in self._jobs]

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status.is_final:
                return
            if job_id == self._current:
                self._cancel.set()
                job.message = "Stopping…"
            else:
                try:
                    self._pending.remove(job_id)
                except ValueError:
                    pass
                job.status = Status.CANCELLED
                job.finished_at = time.time()
        self._emit("job", job)

    def forget(self, job_id: str) -> None:
        """Drop a finished job from the list."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or not job.status.is_final:
                return
            self._jobs.pop(job_id, None)
            if job_id in self._order:
                self._order.remove(job_id)
        self._emit("job", job)

    def clear_finished(self) -> list[Job]:
        with self._lock:
            done = [self._jobs[i] for i in list(self._order)
                    if self._jobs[i].status.is_final]
            for job in done:
                self._jobs.pop(job.id, None)
                self._order.remove(job.id)
        for job in done:
            self._emit("job", job)
        return done

    # -- worker ------------------------------------------------------------
    def _run(self) -> None:
        while not self._shutdown:
            with self._lock:
                job_id = self._pending.popleft() if self._pending else None
                job = self._jobs.get(job_id) if job_id else None
            if job is None:
                self._emit("idle", None)
                self._wake.wait()
                self._wake.clear()
                continue

            self._current = job.id
            self._cancel.clear()
            try:
                self._process(job)
            except Exception as exc:  # worker must never die
                job.status = Status.FAILED
                job.message = str(exc)
                job.finished_at = time.time()
                self._emit("job", job)
            finally:
                self._current = None

    def _log(self, job: Job, line: str) -> None:
        line = line.strip()
        if line:
            self._emit("log", (job.id, line))

    def _process(self, job: Job) -> None:
        job.started_at = time.time()

        if self._ffmpeg_path is None:
            def status(message: str, percent: float) -> None:
                self._emit("ffmpeg", (message, percent))
            self._ffmpeg_path = ensure_ffmpeg(status)

        job.status = Status.PROBING
        job.message = ""
        self._emit("job", job)

        try:
            title, is_playlist, count = probe(job.url)
        except Exception as exc:
            job.status = Status.FAILED
            job.message = f"Could not read that link: {exc}"
            job.finished_at = time.time()
            self._emit("job", job)
            self._log(job, job.message)
            return

        job.title = title or short_url(job.url)
        job.is_playlist = is_playlist
        job.item_count = count
        if self._cancel.is_set():
            self._finish_cancelled(job)
            return

        folder = sanitize_name(job.title) if is_playlist else None
        job.dest_dir = resolve_destination(job, folder)
        job.status = Status.DOWNLOADING
        self._emit("job", job)
        self._log(job, f"Saving to {job.dest_dir}")

        opts = build_options(job, job.dest_dir, self._ffmpeg_path,
                             lambda d: self._on_progress(job, d),
                             lambda line: self._log(job, line))

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                retcode = ydl.download([job.url])
        except DownloadCancelled:
            self._finish_cancelled(job)
            return
        except Exception as exc:
            job.status = Status.FAILED
            job.message = str(exc)
            job.finished_at = time.time()
            self._emit("job", job)
            return

        job.finished_at = time.time()
        if retcode:
            job.status = Status.FAILED
            job.message = "Some items failed — see activity log."
        else:
            job.status = Status.DONE
            job.percent = 1.0
            job.message = ""
        self._emit("job", job)

    def _finish_cancelled(self, job: Job) -> None:
        job.status = Status.CANCELLED
        job.message = "Cancelled"
        job.finished_at = time.time()
        self._emit("job", job)

    def _on_progress(self, job: Job, d: dict) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("cancelled by user")

        status = d.get("status")
        info = d.get("info_dict") or {}
        index = info.get("playlist_index")
        if index:
            job.item_index = index

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            job.status = Status.DOWNLOADING
            job.total = total
            job.downloaded = downloaded
            job.percent = (downloaded / total) if total else 0.0
            job.speed = d.get("speed") or 0.0
            job.eta = d.get("eta") or 0
            job.current_file = os.path.basename(
                info.get("title") or d.get("filename") or "")
            self._emit("job", job)
        elif status == "finished":
            job.status = Status.PROCESSING
            job.percent = 1.0
            job.speed = 0.0
            job.eta = 0
            self._emit("job", job)
