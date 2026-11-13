"""Ctrl shortcuts under a non-Latin keyboard layout: python -m unittest discover tests"""

import tkinter as tk
import unittest
from types import SimpleNamespace

from app.main import replay_as_latin


class ReplayAsLatinTest(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.addCleanup(self.root.destroy)
        self.entry = tk.Entry(self.root)
        self.entry.pack()
        self.entry.focus_force()
        self.root.update()

    def press(self, keycode, keysym, widget=None, shift=False, state=None):
        if state is None:
            state = 0x5 if shift else 0x4
        event = SimpleNamespace(keycode=keycode, keysym=keysym,
                                widget=widget or self.entry, state=state)
        result = replay_as_latin(event)
        self.root.update()
        return result

    def test_arabic_ctrl_v_pastes_into_entry(self):
        self.root.clipboard_clear()
        self.root.clipboard_append("https://youtu.be/x")
        self.assertEqual(self.press(86, "Arabic_ra"), "break")
        self.assertEqual(self.entry.get(), "https://youtu.be/x")

    def test_arabic_shortcuts_reach_app_bindings(self):
        hits = []
        self.root.bind("<Control-n>", lambda _e: hits.append("n"))
        self.root.bind("<Control-C>", lambda _e: hits.append("C"))
        self.press(78, "Arabic_alefmaksura", widget=self.root)
        self.press(67, "Arabic_hamzaonyeh", widget=self.root, shift=True)
        self.assertEqual(hits, ["n", "C"])

    def test_altgr_typing_is_left_alone(self):
        quits = []
        self.root.bind("<Control-q>", lambda _e: quits.append(1))
        # German AltGr+Q types "@"; Windows reports it as Ctrl+Alt+Q.
        self.assertIsNone(self.press(81, "at", widget=self.root,
                                     state=0x20004))
        self.assertEqual(quits, [])

    def test_latin_layout_is_left_alone(self):
        self.assertIsNone(self.press(86, "v"))
        self.assertIsNone(self.press(112, "F1"))  # not a letter or digit
        self.assertEqual(self.entry.get(), "")


if __name__ == "__main__":
    unittest.main()
