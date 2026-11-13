"""Engine state machine: python -m unittest discover tests"""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from app import core
from app.core import Engine, Job, Status


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: reports progress, never touches the net."""

    on_hook = None  # set per test: called after each progress tick

    def __init__(self, opts):
        self.hook = opts["progress_hooks"][0]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        for done in (25, 50, 75, 100):
            self.hook({"status": "downloading", "downloaded_bytes": done,
                       "total_bytes": 100, "info_dict": {"title": "clip"}})
            if FakeYDL.on_hook:
                FakeYDL.on_hook()
        self.hook({"status": "finished", "info_dict": {}})
        return 0


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, value in (("ensure_ffmpeg", lambda _cb: "ffmpeg"),
                              ("probe", lambda _url: ("Clip", False, 1))):
            patcher = mock.patch.object(core, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(core.yt_dlp, "YoutubeDL", FakeYDL)
        patcher.start()
        self.addCleanup(patcher.stop)
        FakeYDL.on_hook = None

    def run_job(self) -> Job:
        finished = threading.Event()

        def emit(event, payload):
            if event == "job" and payload.status.is_final:
                finished.set()

        self.engine = Engine(emit)
        self.engine.start()
        self.addCleanup(self.engine.shutdown)
        job = self.engine.submit(Job(url="https://example.com/v", quality_id="720",
                                     container="mp4", output_dir=self.tmp.name))
        self.assertTrue(finished.wait(5), "job never finished")
        return job

    def test_success_ends_done(self):
        job = self.run_job()
        self.assertIs(job.status, Status.DONE)
        self.assertEqual(job.percent, 1.0)
        self.assertEqual(job.title, "Clip")

    def test_unreadable_link_ends_failed(self):
        def boom(_url):
            raise RuntimeError("404")
        with mock.patch.object(core, "probe", boom):
            job = self.run_job()
        self.assertIs(job.status, Status.FAILED)
        self.assertIn("404", job.message)

    def test_cancel_mid_download_ends_cancelled(self):
        FakeYDL.on_hook = lambda: self.engine.cancel(self.engine.jobs()[0].id)
        job = self.run_job()
        self.assertIs(job.status, Status.CANCELLED)

    def test_cancel_during_ffmpeg_fetch_ends_cancelled(self):
        def slow_fetch(report):
            self.engine.cancel(self.engine.jobs()[0].id)
            report("Downloading ffmpeg… 1%", 0.01)  # engine aborts here
            self.fail("fetch kept going after cancel")

        with mock.patch.object(core, "ensure_ffmpeg", slow_fetch):
            job = self.run_job()
        self.assertIs(job.status, Status.CANCELLED)

    def test_single_video_failure_message(self):
        with mock.patch.object(FakeYDL, "download", lambda _self, _urls: 1):
            job = self.run_job()
        self.assertIs(job.status, Status.FAILED)
        self.assertTrue(job.message.startswith("Download failed"), job.message)


class FfmpegProgressTest(unittest.TestCase):
    def test_reports_once_per_percent(self):
        reports = []

        def fake_retrieve(_url, _path, reporthook):
            for block in range(5000):  # 5000 blocks of a 4000-block file
                reporthook(block, 8192, 8192 * 4000)
            raise OSError("stop before extracting")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(core, "PROJECT_ROOT", Path(tmp)), \
                mock.patch.object(core, "FFMPEG_DIR", Path(tmp) / "bin"), \
                mock.patch.object(core.shutil, "which", lambda _name: None), \
                mock.patch.object(core.urllib.request, "urlretrieve",
                                  fake_retrieve):
            with self.assertRaises(OSError):
                core.ensure_ffmpeg(lambda msg, pct: reports.append(msg))

        progress = [m for m in reports if m.endswith("%")]
        self.assertEqual(len(progress), 101)  # 0% .. 100%, not 5000 lines


if __name__ == "__main__":
    unittest.main()
