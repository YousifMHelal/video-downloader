"""Persisted settings and download history (plain JSON next to the app)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .core import CONTAINERS, QUALITY_BY_ID, Job, default_download_dir

CONFIG_DIR = Path(__file__).resolve().parent.parent / ".config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
HISTORY_LIMIT = 300


def _read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _write(path: Path, payload) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass  # a read-only install should not take the app down


@dataclass
class Settings:
    output_dir: str = field(default_factory=default_download_dir)
    quality_id: str = "1080"
    container: str = "mp4"
    appearance: str = "system"
    window_width: int = 1100
    window_height: int = 640

    @classmethod
    def load(cls) -> "Settings":
        data = _read(SETTINGS_FILE, {})
        settings = cls()
        if isinstance(data, dict):
            for key, minimum in (("window_width", 880), ("window_height", 540)):
                value = data.get(key)
                if isinstance(value, int) and value >= minimum:
                    setattr(settings, key, value)
            if isinstance(data.get("output_dir"), str) and data["output_dir"]:
                settings.output_dir = data["output_dir"]
            if data.get("quality_id") in QUALITY_BY_ID:
                settings.quality_id = data["quality_id"]
            if data.get("container") in CONTAINERS:
                settings.container = data["container"]
            if data.get("appearance") in ("system", "light", "dark"):
                settings.appearance = data["appearance"]
        return settings

    def save(self) -> None:
        _write(SETTINGS_FILE, asdict(self))


@dataclass
class HistoryEntry:
    title: str
    url: str
    quality_id: str
    container: str
    dest_dir: str
    status: str
    items: int
    bytes: int
    finished_at: float

    @classmethod
    def from_job(cls, job: Job) -> "HistoryEntry":
        return cls(
            title=job.display_title,
            url=job.url,
            quality_id=job.quality_id,
            container=job.container,
            dest_dir=job.dest_dir,
            status=job.status.value,
            items=job.item_count,
            bytes=job.total,
            finished_at=job.finished_at or time.time(),
        )


class History:
    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        raw = _read(HISTORY_FILE, [])
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                try:
                    self._entries.append(HistoryEntry(**item))
                except TypeError:
                    continue

    def entries(self) -> list[HistoryEntry]:
        """Newest first."""
        return sorted(self._entries, key=lambda e: e.finished_at, reverse=True)

    def add(self, job: Job) -> HistoryEntry:
        entry = HistoryEntry.from_job(job)
        self._entries.append(entry)
        del self._entries[:-HISTORY_LIMIT]
        self.save()
        return entry

    def clear(self) -> None:
        self._entries.clear()
        self.save()

    def save(self) -> None:
        _write(HISTORY_FILE, [asdict(e) for e in self._entries])


def relative_time(stamp: float) -> str:
    delta = max(0, time.time() - stamp)
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = int(delta // 60)
        return f"{minutes} min ago"
    if delta < 86400:
        hours = int(delta // 3600)
        return f"{hours} hr ago" if hours > 1 else "1 hr ago"
    days = int(delta // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return time.strftime("%d %b %Y", time.localtime(stamp))
