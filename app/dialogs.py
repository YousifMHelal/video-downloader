"""Modal windows: adding a download, and the about box."""

from __future__ import annotations

import math
from tkinter import filedialog

import customtkinter as ctk

from . import theme as t
from .core import (CONTAINER_LABELS, CONTAINERS, QUALITY_BY_ID,
                   QUALITY_BY_LABEL, QUALITY_LABELS, looks_like_url)
from .widgets import (divider, entry, field_label, hint_label, option_menu,
                      primary_button, secondary_button, value_box)


class Dialog(ctk.CTkToplevel):
    """Shared behaviour: modal, centred on the parent, Esc closes.

    Subclasses build their content, then call ``_fit()`` so the window is
    exactly as tall as what it holds; a fixed height clipped the buttons
    whenever fonts or DPI scaling made the content taller.
    """

    def __init__(self, parent, title: str, width: int):
        super().__init__(parent)
        self.title(title)
        self.configure(fg_color=t.BG)
        self.resizable(False, False)
        self.transient(parent)
        self._parent = parent
        self._width = width
        self._fit(height=240)

        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(60, self._grab)

    def _fit(self, height: int | None = None) -> None:
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scaling = 1.0
        self.update_idletasks()
        if height is None:
            height = math.ceil(self.winfo_reqheight() / scaling)
        parent = self._parent
        x = (parent.winfo_rootx()
             + (parent.winfo_width() - int(self._width * scaling)) // 2)
        y = parent.winfo_rooty() + 90
        self.geometry(f"{self._width}x{height}+{max(0, x)}+{max(0, y)}")

    def _grab(self) -> None:
        try:
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            pass


class AddDownloadDialog(Dialog):
    """Add one link, with the options to use for it."""

    def __init__(self, parent, settings, on_submit, initial_url: str = ""):
        super().__init__(parent, "Add download", 520)
        self._on_submit = on_submit
        self.output_dir = settings.output_dir
        self.grid_columnconfigure(0, weight=1)
        fonts = t.fonts()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=t.XL, pady=(t.XL, 0))
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text="Link", font=fonts.small_strong,
                     text_color=t.TEXT, anchor="w").grid(row=0, column=0,
                                                         sticky="w")
        self.url_entry = entry(body, "https://…", height=38)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="ew",
                            pady=(t.XS, 0))
        if initial_url:
            self.url_entry.insert(0, initial_url)
        self.url_entry.bind("<Return>", lambda _e: self._submit())

        # Reserves one short line, so an error does not resize the window.
        self.error_label = hint_label(body, "")
        self.error_label.configure(text_color=t.DANGER, height=18)
        self.error_label.grid(row=2, column=0, sticky="w", pady=(t.XS, 0))

        divider(body).grid(row=3, column=0, columnspan=2, sticky="ew",
                           pady=t.MD)

        options = ctk.CTkFrame(body, fg_color="transparent")
        options.grid(row=4, column=0, columnspan=2, sticky="ew")
        options.grid_columnconfigure(2, weight=1)

        quality_box = ctk.CTkFrame(options, fg_color="transparent")
        quality_box.grid(row=0, column=0, sticky="nw")
        field_label(quality_box, "Quality").grid(row=0, column=0, sticky="w")
        self.quality_var = ctk.StringVar(
            value=QUALITY_BY_ID[settings.quality_id].label)
        option_menu(quality_box, QUALITY_LABELS, self._on_quality,
                    self.quality_var, width=160).grid(row=1, column=0,
                                                      pady=(t.XS, 0))

        format_box = ctk.CTkFrame(options, fg_color="transparent")
        format_box.grid(row=0, column=1, sticky="nw", padx=(t.MD, 0))
        field_label(format_box, "Format").grid(row=0, column=0, sticky="w")
        self.container_var = ctk.StringVar(
            value=dict(zip(CONTAINERS, CONTAINER_LABELS))[settings.container])
        self.container_menu = option_menu(format_box, CONTAINER_LABELS, None,
                                          self.container_var, width=104)
        self.container_menu.grid(row=1, column=0, pady=(t.XS, 0))

        folder_box = ctk.CTkFrame(body, fg_color="transparent")
        folder_box.grid(row=5, column=0, columnspan=2, sticky="ew",
                        pady=(t.MD, 0))
        folder_box.grid_columnconfigure(0, weight=1)
        field_label(folder_box, "Save to").grid(row=0, column=0, sticky="w")
        self.folder_label = value_box(folder_box, self.output_dir)
        self.folder_label.grid(row=1, column=0, sticky="ew", pady=(t.XS, 0))
        secondary_button(folder_box, "Browse…", self._browse, width=92).grid(
            row=1, column=1, padx=(t.SM, 0), pady=(t.XS, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=1, column=0, sticky="ew", padx=t.XL, pady=t.XL)
        footer.grid_columnconfigure(0, weight=1)
        secondary_button(footer, "Cancel", self.destroy, width=96).grid(
            row=0, column=1, padx=(0, t.SM))
        primary_button(footer, "Add download", self._submit, width=132).grid(
            row=0, column=2)

        self._sync_container_state()
        self._fit()
        self.after(120, self.url_entry.focus_set)

    def _on_quality(self, _label: str) -> None:
        self._sync_container_state()

    def _sync_container_state(self) -> None:
        quality = QUALITY_BY_LABEL.get(self.quality_var.get())
        self.container_menu.configure(
            state="disabled" if quality and quality.audio_only else "normal")

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir,
                                         title="Choose a download folder",
                                         parent=self)
        if chosen:
            self.output_dir = chosen
            self.folder_label.configure(text=f"  {chosen}")

    def _submit(self) -> None:
        url = self.url_entry.get().strip()
        if not looks_like_url(url):
            self.error_label.configure(text="That does not look like a link.")
            return
        quality = QUALITY_BY_LABEL[self.quality_var.get()]
        container = dict(zip(CONTAINER_LABELS, CONTAINERS))[
            self.container_var.get()]
        self._on_submit(url, quality.id, container, self.output_dir)
        self.destroy()


class AboutDialog(Dialog):
    def __init__(self, parent, version: str, data_dir: str):
        super().__init__(parent, "About", 420)
        self.grid_columnconfigure(0, weight=1)
        fonts = t.fonts()

        ctk.CTkLabel(self, text="Video Downloader", font=fonts.display,
                     text_color=t.TEXT).grid(row=0, column=0, pady=(t.XL, 0))
        ctk.CTkLabel(self, text=f"Version {version}", font=fonts.small,
                     text_color=t.TEXT_FAINT).grid(row=1, column=0)
        ctk.CTkLabel(
            self, text="Downloads videos, audio and playlists using yt-dlp "
                       "and ffmpeg.", font=fonts.body, text_color=t.TEXT_DIM,
            wraplength=340, justify="center").grid(row=2, column=0,
                                                   padx=t.XL, pady=t.MD)
        ctk.CTkLabel(self, text=data_dir, font=fonts.small,
                     text_color=t.TEXT_FAINT, wraplength=340).grid(row=3,
                                                                   column=0)
        primary_button(self, "Close", self.destroy, width=110).grid(
            row=4, column=0, pady=t.XL)
        self._fit()
