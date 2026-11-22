"""System clipboard write: python -m unittest discover tests"""

import subprocess
import sys
import unittest

from app.core import set_clipboard_text


class SetClipboardTextTest(unittest.TestCase):
    def test_text_survives_this_process(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        url = "https://example.com/watch?v=aB_1-é"
        self.assertTrue(set_clipboard_text(url))
        # Read it from a separate process: that is what pasting elsewhere does.
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.stdout.strip(), url)

    def test_empty_text_refused(self):
        self.assertFalse(set_clipboard_text(""))
