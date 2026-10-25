"""Reusable presentation components built on CustomTkinter primitives."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from typing import Callable

import customtkinter as ctk

from . import theme as t
from .core import Status

STATUS_TONE: dict[Status, tuple[tuple[str, str], tuple[str, str]]] = {
    Status.QUEUED: (t.TEXT_DIM, t.SURFACE_SUNKEN),
    Status.PROBING: (t.ACCENT, t.ACCENT_SOFT),
    Status.DOWNLOADING: (t.ACCENT, t.ACCENT_SOFT),
    Status.PROCESSING: (t.WARN, t.WARN_SOFT),
    Status.DONE: (t.SUCCESS, t.SUCCESS_SOFT),
    Status.FAILED: (t.DANGER, t.DANGER_SOFT),
    Status.CANCELLED: (t.TEXT_DIM, t.SURFACE_SUNKEN),
}


def reveal(path: str) -> None:
    """Open a folder in the system file browser."""
    if not path or not os.path.isdir(path):
        return
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - user-initiated, local path
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def elide(text: str, limit: int) -> str:
    """Tk labels clip rather than ellipsize, so shorten long text ourselves."""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fit_text(text: str, font, width: float, keep_end: bool = False) -> str:
    """Shorten text with an ellipsis until it measures at most ``width``
    pixels in ``font``. ``keep_end`` trims from the front, which suits paths."""
    text = text.strip()
    if width <= 0:
        return ""
    if font.measure(text) <= width:
        return text

    def shortened(length: int) -> str:
        if keep_end:
            return "…" + text[len(text) - length:].lstrip()
        return text[:length].rstrip() + "…"

    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(shortened(middle)) <= width:
            low = middle
        else:
            high = middle - 1
    return shortened(low)


# ── Containers ──────────────────────────────────────────────────────────────
class Card(ctk.CTkFrame):
    """A bordered surface — the only way content gets a background."""

    def __init__(self, master, raised: bool = False, **kwargs):
        kwargs.setdefault("fg_color", t.SURFACE_RAISED if raised else t.SURFACE)
        kwargs.setdefault("corner_radius", t.R_CARD)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", t.BORDER)
        super().__init__(master, **kwargs)


class Dot(ctk.CTkFrame):
    """Small status marker; reads as a colour even at a glance."""

    def __init__(self, master, tone: tuple[str, str] = t.TEXT_FAINT,
                 size: int = 8):
        super().__init__(master, width=size, height=size, corner_radius=size // 2,
                         fg_color=tone)
        self.grid_propagate(False)
        self._tone = tone

    def set_tone(self, tone: tuple[str, str]) -> None:
        # Called on every status tick; a redraw only when it changes.
        if tone != self._tone:
            self._tone = tone
            self.configure(fg_color=tone)


# ── Controls ────────────────────────────────────────────────────────────────
def primary_button(master, text: str, command, width: int = 112,
                   height: int = t.H_BUTTON) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width,
                         height=height, corner_radius=t.R_CTRL,
                         fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER,
                         text_color=t.TEXT_ON_ACCENT,
                         font=t.fonts().body_strong)


def secondary_button(master, text: str, command, width: int = 112,
                     height: int = t.H_BUTTON) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width,
                         height=height, corner_radius=t.R_CTRL,
                         fg_color=t.SURFACE, hover_color=t.HOVER,
                         border_width=1, border_color=t.BORDER_STRONG,
                         text_color=t.TEXT, font=t.fonts().body)


def danger_button(master, text: str, command, width: int = 112,
                  height: int = t.H_BUTTON) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=width,
                         height=height, corner_radius=t.R_CTRL,
                         fg_color="transparent", hover_color=t.DANGER_SOFT,
                         border_width=1, border_color=t.DANGER,
                         text_color=t.DANGER, font=t.fonts().body)


def link_button(master, text: str, command) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, width=1, height=22,
                         corner_radius=t.XS, fg_color="transparent",
                         hover_color=t.HOVER, text_color=t.ACCENT,
                         font=t.fonts().small_strong)


def icon_button(master, glyph: str, command, tone=t.TEXT_FAINT,
                hover=t.HOVER, size: int = 28) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=glyph, command=command, width=size,
                         height=size, corner_radius=t.R_CTRL,
                         fg_color="transparent", hover_color=hover,
                         text_color=tone, font=t.fonts().body_strong)


def entry(master, placeholder: str = "", **kwargs) -> ctk.CTkEntry:
    kwargs.setdefault("height", t.H_CTRL)
    kwargs.setdefault("corner_radius", t.R_CTRL)
    return ctk.CTkEntry(master, placeholder_text=placeholder,
                        fg_color=t.SURFACE_SUNKEN, border_color=t.BORDER_STRONG,
                        border_width=1, text_color=t.TEXT,
                        placeholder_text_color=t.TEXT_FAINT,
                        font=t.fonts().body, **kwargs)


def option_menu(master, values, command=None, variable=None,
                width: int = 150, height: int = t.H_CTRL) -> ctk.CTkOptionMenu:
    return ctk.CTkOptionMenu(
        master, values=list(values), command=command, variable=variable,
        width=width, height=height, corner_radius=t.R_CTRL,
        fg_color=t.SURFACE_SUNKEN, button_color=t.SURFACE_SUNKEN,
        button_hover_color=t.HOVER, text_color=t.TEXT, font=t.fonts().body,
        dropdown_fg_color=t.SURFACE_RAISED, dropdown_hover_color=t.HOVER,
        dropdown_text_color=t.TEXT, dropdown_font=t.fonts().body)


def scroll_area(master) -> ctk.CTkScrollableFrame:
    area = ctk.CTkScrollableFrame(
        master, fg_color="transparent", corner_radius=0,
        scrollbar_button_color=t.BORDER_STRONG,
        scrollbar_button_hover_color=t.TEXT_FAINT)
    area.grid_columnconfigure(0, weight=1)
    return area


def field_label(master, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text.upper(), font=t.fonts().label,
                        text_color=t.TEXT_FAINT, anchor="w")


def hint_label(master, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, font=t.fonts().small,
                        text_color=t.TEXT_FAINT, anchor="w", justify="left")


def value_box(master, text: str = "") -> ctk.CTkLabel:
    """Read-only field that still looks like an input."""
    return ctk.CTkLabel(master, text=f"  {text}", font=t.fonts().body,
                        text_color=t.TEXT_DIM, anchor="w", height=t.H_CTRL,
                        fg_color=t.SURFACE_SUNKEN, corner_radius=t.R_CTRL)


def divider(master, vertical: bool = False, length: int = 40) -> ctk.CTkFrame:
    """Hairline rule. A vertical rule needs an explicit length, otherwise the
    frame's default height would stretch the row it sits in."""
    # A rounded corner on a 1px frame leaves nothing to draw, so the rule
    # would vanish; it has to be square.
    if vertical:
        return ctk.CTkFrame(master, width=1, height=length, corner_radius=0,
                            fg_color=t.BORDER)
    return ctk.CTkFrame(master, height=1, corner_radius=0, fg_color=t.BORDER)


def popup_menu(master) -> tk.Menu:
    """A native context menu, themed to match the window."""
    dark = ctk.get_appearance_mode() == "Dark"
    index = 1 if dark else 0
    return tk.Menu(master, tearoff=0,
                   bg=t.SURFACE_RAISED[index], fg=t.TEXT[index],
                   activebackground=t.ACCENT[index],
                   activeforeground="#FFFFFF",
                   disabledforeground=t.TEXT_FAINT[index],
                   borderwidth=0, activeborderwidth=0,
                   font=("Segoe UI", 9))


class SearchField(ctk.CTkFrame):
    """Filter box with a leading glyph and a clear button."""

    def __init__(self, master, on_change: Callable[[str], None],
                 placeholder: str = "Filter…", width: int = 200):
        super().__init__(master, fg_color=t.SURFACE_SUNKEN,
                         corner_radius=t.R_CTRL, height=t.H_CTRL, width=width)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self._on_change = on_change

        ctk.CTkLabel(self, text="⌕", width=18, font=t.fonts().body_strong,
                     text_color=t.TEXT_FAINT).grid(row=0, column=0,
                                                   padx=(t.SM, 0))
        # No textvariable: CustomTkinter never shows the placeholder of an
        # entry bound to one.
        self.entry = ctk.CTkEntry(
            self, placeholder_text=placeholder,
            height=t.H_CTRL - 8, border_width=0, fg_color="transparent",
            text_color=t.TEXT, placeholder_text_color=t.TEXT_FAINT,
            font=t.fonts().small)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.entry.bind("<KeyRelease>", lambda _e: self._changed())
        self.clear_button = icon_button(self, "✕", self.clear, size=22)
        self.clear_button.grid(row=0, column=2, padx=(0, t.XS))
        self._text = ""

    def _changed(self) -> None:
        text = self.entry.get()
        if text != self._text:
            self._text = text
            self._on_change(text)

    def clear(self) -> None:
        self.entry.delete(0, "end")
        self._changed()
        if self.focus_get() is not self.entry._entry:
            self.entry._activate_placeholder()

    def focus(self) -> None:
        self.entry.focus_set()


class Toolbar(ctk.CTkFrame):
    """Action strip above a list, the way desktop apps place one."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent", height=t.TOOLBAR_H)
        self._column = 0

    def add(self, widget, pad: int = t.XS, weight: int = 0, sticky: str = "w"):
        widget.grid(row=0, column=self._column, padx=(0, pad), sticky=sticky)
        if weight:
            self.grid_columnconfigure(self._column, weight=weight)
        self._column += 1
        return widget

    def add_separator(self) -> None:
        self.add(divider(self, vertical=True, length=22), pad=t.MD)

    def add_spacer(self) -> None:
        spacer = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.add(spacer, pad=0, weight=1, sticky="ew")


class StatusBar(ctk.CTkFrame):
    """Bottom strip: state on the left, totals on the right."""

    def __init__(self, master, on_toggle_log):
        super().__init__(master, fg_color=t.SIDEBAR, corner_radius=0,
                         height=t.STATUS_H)
        self.grid_propagate(False)
        self.grid_columnconfigure(2, weight=1)
        ctk.CTkFrame(self, height=1, fg_color=t.BORDER).place(
            x=0, y=0, relwidth=1)

        self.dot = Dot(self, t.TEXT_FAINT, size=7)
        self.dot.grid(row=0, column=0, padx=(t.MD, t.SM))
        self.state_label = ctk.CTkLabel(self, text="", font=t.fonts().small,
                                        text_color=t.TEXT_DIM, anchor="w")
        self.state_label.grid(row=0, column=1, sticky="w")

        self.totals_label = ctk.CTkLabel(self, text="", font=t.fonts().small,
                                         text_color=t.TEXT_FAINT, anchor="e")
        self.totals_label.grid(row=0, column=3, sticky="e", padx=(0, t.SM))

        self.log_button = ctk.CTkButton(
            self, text="Activity", width=74, height=20, corner_radius=6,
            fg_color="transparent", hover_color=t.HOVER,
            text_color=t.TEXT_FAINT, font=t.fonts().small,
            command=on_toggle_log)
        self.log_button.grid(row=0, column=4, padx=(0, t.MD))

    # The app refreshes these several times a second; reconfiguring a label
    # re-lays out the bar even when the text is the same.
    def set_state(self, text: str, tone: tuple[str, str]) -> None:
        if text != self.state_label.cget("text"):
            self.state_label.configure(text=text)
        self.dot.set_tone(tone)

    def set_totals(self, text: str) -> None:
        if text != self.totals_label.cget("text"):
            self.totals_label.configure(text=text)

    def set_log_open(self, open_: bool) -> None:
        self.log_button.configure(text="Activity ▾" if open_ else "Activity ▸",
                                  text_color=t.TEXT if open_ else t.TEXT_FAINT)
