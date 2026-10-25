"""Application shell: window chrome, menus, navigation and controller wiring."""

from __future__ import annotations

import queue
import sys
import tkinter as tk
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import theme as t
from .core import (CONTAINER_LABELS, CONTAINERS, FFMPEG_DIR, PROJECT_ROOT,
                   QUALITY_BY_LABEL, Engine, Job, Status, ffmpeg_present,
                   human_speed, looks_like_url)
from .dialogs import AboutDialog, AddDownloadDialog
from .store import CONFIG_DIR, History, HistoryEntry, Settings
from .views import HistoryView, QueueView, SettingsView
from .widgets import Card, Dot, StatusBar, divider, reveal

APP_TITLE = "Video Downloader"
VERSION = "2.0"
NAV_ITEMS = (("queue", "Queue"), ("history", "History"), ("settings", "Settings"))


def asset_dir() -> Path:
    """Assets live beside the source, or inside the PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) / "assets" if bundled else PROJECT_ROOT / "assets"


class NavItem(ctk.CTkFrame):
    """Sidebar entry: accent rail, label, and an optional count badge."""

    def __init__(self, master, label: str, command):
        super().__init__(master, fg_color="transparent", height=t.H_NAV)
        self.grid_columnconfigure(1, weight=1)

        self.rail = ctk.CTkFrame(self, width=3, height=18, corner_radius=2,
                                 fg_color="transparent")
        self.rail.grid(row=0, column=0, sticky="w")

        self.button = ctk.CTkButton(
            self, text=label, command=command, height=t.H_NAV,
            corner_radius=t.R_CTRL, anchor="w", fg_color="transparent",
            hover_color=t.HOVER, text_color=t.TEXT_DIM, font=t.fonts().body)
        self.button.grid(row=0, column=1, sticky="ew", padx=(t.SM, 0))

        self.badge = ctk.CTkLabel(self, text="", width=22, height=18,
                                  corner_radius=9, fg_color=t.ACCENT_SOFT,
                                  text_color=t.ACCENT, font=t.fonts().label)
        self.badge.grid(row=0, column=2, padx=(t.XS, 0))
        self.badge.grid_remove()
        self._count = 0

    def set_active(self, active: bool) -> None:
        self.rail.configure(fg_color=t.ACCENT if active else "transparent")
        self.button.configure(
            fg_color=t.ACCENT_SOFT if active else "transparent",
            text_color=t.ACCENT if active else t.TEXT_DIM,
            font=t.fonts().body_strong if active else t.fonts().body)

    def set_count(self, count: int) -> None:
        # Called on every status tick; re-gridding re-lays out the sidebar.
        if count == self._count:
            return
        self._count = count
        if count:
            self.badge.configure(text=str(count))
            self.badge.grid()
        else:
            self.badge.grid_remove()


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_select, on_add):
        super().__init__(master, fg_color=t.SIDEBAR, corner_radius=0,
                         width=t.SIDEBAR_W)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        fonts = t.fonts()

        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=t.MD, pady=(t.LG, t.LG))
        brand.grid_columnconfigure(1, weight=1)
        self._mark(brand).grid(row=0, column=0, rowspan=2, padx=(t.XS, t.SM))
        ctk.CTkLabel(brand, text="Downloader", font=fonts.subtitle,
                     text_color=t.TEXT, anchor="w").grid(row=0, column=1,
                                                         sticky="w")
        ctk.CTkLabel(brand, text=f"version {VERSION}", font=fonts.small,
                     text_color=t.TEXT_FAINT, anchor="w").grid(row=1, column=1,
                                                               sticky="w")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=t.SM)
        nav.grid_columnconfigure(0, weight=1)
        self.items: dict[str, NavItem] = {}
        for index, (key, label) in enumerate(NAV_ITEMS):
            item = NavItem(nav, label, lambda k=key: on_select(k))
            item.grid(row=index, column=0, sticky="ew", pady=1)
            self.items[key] = item

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=t.SM, pady=(0, t.MD))
        footer.grid_columnconfigure(0, weight=1)
        divider(footer).grid(row=0, column=0, sticky="ew", padx=t.XS,
                             pady=(0, t.MD))
        ctk.CTkButton(footer, text="+  Add download", command=on_add,
                      height=t.H_BUTTON, corner_radius=t.R_CTRL,
                      fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER,
                      text_color=t.TEXT_ON_ACCENT,
                      font=fonts.body_strong).grid(row=1, column=0, sticky="ew",
                                                   padx=t.XS)

    def _mark(self, master):
        icon = asset_dir() / "icon.png"
        if icon.exists():
            try:
                from PIL import Image
                image = ctk.CTkImage(Image.open(icon), size=(30, 30))
                return ctk.CTkLabel(master, text="", image=image)
            except Exception:
                pass
        return ctk.CTkLabel(master, text="↓", width=30, height=30,
                            corner_radius=9, fg_color=t.ACCENT,
                            text_color=t.TEXT_ON_ACCENT, font=t.fonts().mark)

    def select(self, key: str) -> None:
        for name, item in self.items.items():
            item.set_active(name == key)

    def set_queue_count(self, count: int) -> None:
        self.items["queue"].set_count(count)


class ActivityLog(Card):
    """Collapsible transcript of everything yt-dlp reported."""

    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=t.MD, pady=(t.SM, 0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="ACTIVITY", font=t.fonts().label,
                     text_color=t.TEXT_FAINT).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text="Clear", width=48, height=20, corner_radius=6,
                      fg_color="transparent", hover_color=t.HOVER,
                      text_color=t.ACCENT, font=t.fonts().small_strong,
                      command=self.clear).grid(row=0, column=1, sticky="e")

        self.box = ctk.CTkTextbox(
            self, height=130, corner_radius=t.R_CTRL, border_width=0,
            fg_color=t.SURFACE_SUNKEN, text_color=t.TEXT_DIM,
            font=t.fonts().mono, activate_scrollbars=True,
            scrollbar_button_color=t.BORDER_STRONG)
        self.box.grid(row=1, column=0, sticky="nsew", padx=t.MD,
                      pady=(t.SM, t.MD))
        self.box.configure(state="disabled")

    def append(self, line: str) -> None:
        self.box.configure(state="normal")
        self.box.insert("end", line + "\n")
        self.box.see("end")
        self.box.configure(state="disabled")

    def clear(self) -> None:
        self.box.configure(state="normal")
        self.box.delete("0.0", "end")
        self.box.configure(state="disabled")


class Toast(Card):
    """Transient message, shown over the content area."""

    def __init__(self, master):
        super().__init__(master, raised=True)
        self.dot = Dot(self, t.ACCENT)
        self.dot.grid(row=0, column=0, padx=(t.MD, t.SM), pady=t.SM)
        self.label = ctk.CTkLabel(self, text="", font=t.fonts().small_strong,
                                  text_color=t.TEXT)
        self.label.grid(row=0, column=1, padx=(0, t.MD), pady=t.SM)
        self._timer: str | None = None

    def show(self, text: str, tone: tuple[str, str] = t.ACCENT) -> None:
        self.label.configure(text=text)
        self.dot.set_tone(tone)
        self.place(relx=1.0, rely=0.0, x=-4, y=4, anchor="ne")
        self.lift()
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(3400, self.hide)

    def hide(self) -> None:
        self._timer = None
        self.place_forget()


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.history = History()
        ctk.set_appearance_mode(self.settings.appearance)

        self.title(APP_TITLE)
        self._restore_geometry()
        self.configure(fg_color=t.BG)
        self._apply_icon()

        self._events: queue.Queue = queue.Queue()
        self.engine = Engine(self._enqueue_event)
        self._recorded: set[str] = set()
        self._selected: str | None = None
        self._log_open = False
        self._current_view = "queue"
        self._clipboard_seen = ""
        self._title_suffix = ""

        self._build()
        self._build_menu()
        self._bind_shortcuts()
        self.engine.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._pump)
        self.bind("<FocusIn>", self._check_clipboard)

        ready = ffmpeg_present()
        self.status.set_state("Ready" if ready else
                              "ffmpeg is fetched on first download",
                              t.SUCCESS if ready else t.WARN)
        self.settings_view.set_ffmpeg_status(
            f"Installed · {FFMPEG_DIR}" if ready
            else "Not installed yet — downloaded automatically.")

    # -- window ------------------------------------------------------------
    def _apply_icon(self) -> None:
        """Window, taskbar and alt-tab icon.

        Windows groups a windowed Python script under python.exe unless the
        process declares its own AppUserModelID, which is why the taskbar would
        otherwise show the Python logo.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "VideoDownloader.App")
            except Exception:
                pass

        icon = asset_dir() / "icon.ico"
        if icon.exists():
            for attempt in (lambda: self.iconbitmap(default=str(icon)),
                            lambda: self.iconbitmap(str(icon))):
                try:
                    attempt()
                except Exception:
                    continue
            self.after(400, lambda: self._reapply_icon(icon))

        png = asset_dir() / "icon.png"
        if png.exists():
            try:
                from PIL import Image, ImageTk
                self._icon_photo = ImageTk.PhotoImage(Image.open(png))
                self.iconphoto(True, self._icon_photo)
            except Exception:
                pass

    def _reapply_icon(self, icon: Path) -> None:
        try:
            self.iconbitmap(str(icon))
        except Exception:
            pass

    def _restore_geometry(self) -> None:
        """Re-open at the remembered size, clamped to this display."""
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scaling = 1.0

        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = int(min(self.settings.window_width, screen_w / scaling - 64))
        height = int(min(self.settings.window_height, screen_h / scaling - 96))
        x = max(0, int((screen_w - width * scaling) / 2))
        y = max(0, int((screen_h - height * scaling) / 3))
        self.minsize(min(1000, width), min(560, height))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _remember_geometry(self) -> None:
        try:
            self.settings.window_width = self.winfo_width()
            self.settings.window_height = self.winfo_height()
        except Exception:
            pass

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, self.show_view, self.open_add_dialog)
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.grid(row=0, column=1, sticky="nsew", padx=t.LG, pady=t.LG)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(0, weight=1)
        self.content = shell

        self.queue_view = QueueView(shell, self, self.settings)
        self.history_view = HistoryView(shell, self)
        self.settings_view = SettingsView(shell, self, self.settings)
        self._views = {
            "queue": self.queue_view,
            "history": self.history_view,
            "settings": self.settings_view,
        }

        self.log = ActivityLog(shell)
        self.toast = Toast(shell)

        self.status = StatusBar(self, self.toggle_log)
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.show_view("queue")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add download…", accelerator="Ctrl+N",
                              command=lambda: self.open_add_dialog())
        file_menu.add_command(label="Add link from clipboard",
                              accelerator="Ctrl+V",
                              command=self.add_from_clipboard)
        file_menu.add_separator()
        file_menu.add_command(label="Open downloads folder",
                              command=lambda: reveal(self.settings.output_dir))
        file_menu.add_command(label="Open data folder",
                              command=self.open_config_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q",
                              command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Copy link", accelerator="Ctrl+Shift+C",
                              command=self.copy_selected_link)
        edit_menu.add_command(label="Cancel download", accelerator="Esc",
                              command=self.cancel_selected)
        edit_menu.add_command(label="Remove from list", accelerator="Del",
                              command=self.remove_selected)
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear finished",
                              command=self.clear_finished)
        edit_menu.add_command(label="Clear history", command=self.clear_history)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Queue", accelerator="Ctrl+1",
                              command=lambda: self.show_view("queue"))
        view_menu.add_command(label="History", accelerator="Ctrl+2",
                              command=lambda: self.show_view("history"))
        view_menu.add_command(label="Settings", accelerator="Ctrl+3",
                              command=lambda: self.show_view("settings"))
        view_menu.add_separator()
        view_menu.add_command(label="Activity log", accelerator="Ctrl+J",
                              command=self.toggle_log)

        theme_menu = tk.Menu(view_menu, tearoff=0)
        for label in ("System", "Light", "Dark"):
            theme_menu.add_command(
                label=label,
                command=lambda value=label: self.set_appearance(value.lower()))
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menubar)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _e: self.open_add_dialog())
        self.bind("<Control-v>", self._shortcut_paste)
        self.bind("<Control-q>", lambda _e: self._on_close())
        self.bind("<Control-j>", lambda _e: self.toggle_log())
        self.bind("<Control-f>", lambda _e: self._focus_filter())
        self.bind("<Control-Key-1>", lambda _e: self.show_view("queue"))
        self.bind("<Control-Key-2>", lambda _e: self.show_view("history"))
        self.bind("<Control-Key-3>", lambda _e: self.show_view("settings"))
        self.bind("<Control-C>", lambda _e: self.copy_selected_link())
        self.bind("<Delete>", self._shortcut_delete)
        self.bind("<Escape>", self._shortcut_escape)

    def _typing(self) -> bool:
        """True when a text field has focus, so shortcuts stay out of the way."""
        widget = self.focus_get()
        return isinstance(widget, (tk.Entry, tk.Text))

    def _shortcut_paste(self, _event):
        if self._typing():
            return None
        self.add_from_clipboard()
        return "break"

    def _shortcut_delete(self, _event):
        if self._typing():
            return None
        self.remove_selected()
        return "break"

    def _shortcut_escape(self, _event):
        if self._typing():
            return None
        if self._selected:
            self.cancel_selected()
        return "break"

    def _focus_filter(self) -> None:
        view = self._views.get(self._current_view)
        if hasattr(view, "search"):
            view.search.focus()

    # -- navigation --------------------------------------------------------
    def show_view(self, key: str) -> None:
        if key not in self._views:
            return
        self._current_view = key
        for name, view in self._views.items():
            if name == key:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_remove()

        if key == "history":
            self.history_view.render(self.history.entries())
        elif key == "settings":
            self.settings_view.sync(self.settings)
        self.sidebar.select(key)

    def toggle_log(self) -> None:
        self._log_open = not self._log_open
        if self._log_open:
            self.log.grid(row=1, column=0, sticky="ew", pady=(t.MD, 0))
        else:
            self.log.grid_remove()
        self.status.set_log_open(self._log_open)

    # -- adding ------------------------------------------------------------
    def open_add_dialog(self, url: str = "") -> None:
        AddDownloadDialog(self, self.settings, self._submit_job, url)

    def _submit_job(self, url: str, quality_id: str, container: str,
                    output_dir: str) -> None:
        self.engine.submit(Job(url=url, quality_id=quality_id,
                               container=container, output_dir=output_dir))
        self.show_view("queue")
        self.queue_view.render(self.engine.jobs())
        self.toast.show("Added to queue", t.ACCENT)

    def add_from_clipboard(self) -> None:
        text = self._clipboard_text()
        if not looks_like_url(text):
            self.toast.show("No link on the clipboard", t.WARN)
            return
        self._clipboard_seen = text
        self.open_add_dialog(text)

    def _clipboard_text(self) -> str:
        try:
            return self.clipboard_get().strip()
        except Exception:
            return ""

    def _check_clipboard(self, _event=None) -> None:
        """Offer a copied link when the window comes back to the front."""
        text = self._clipboard_text()
        if (text and text != self._clipboard_seen and looks_like_url(text)
                and not any(j.url == text for j in self.engine.jobs())):
            self._clipboard_seen = text
            self.toast.show("Link copied — press Ctrl+V to add", t.ACCENT)

    def requeue(self, record: HistoryEntry) -> None:
        self._submit_job(record.url, record.quality_id, record.container,
                         self.settings.output_dir)
        self.toast.show("Queued again", t.ACCENT)

    # -- selection and row actions -----------------------------------------
    def select_job(self, job_id: str | None) -> None:
        self._selected = job_id
        self.queue_view.sync_selection(job_id)

    def _job(self, job_id: str | None) -> Job | None:
        if not job_id:
            return None
        return next((j for j in self.engine.jobs() if j.id == job_id), None)

    def row_action(self, job_id: str) -> None:
        """The ✕ on a row: cancel while running, remove once finished."""
        job = self._job(job_id)
        if job is None:
            return
        if job.status.is_final:
            self.forget_job(job_id)
        else:
            self.cancel_job(job_id)

    def cancel_job(self, job_id: str) -> None:
        self.engine.cancel(job_id)

    def forget_job(self, job_id: str) -> None:
        if self._selected == job_id:
            self._selected = None
        self.engine.forget(job_id)
        self.queue_view.render(self.engine.jobs())

    def cancel_selected(self) -> None:
        job = self._job(self._selected)
        if job and not job.status.is_final:
            self.cancel_job(job.id)

    def remove_selected(self) -> None:
        job = self._job(self._selected)
        if job and job.status.is_final:
            self.forget_job(job.id)

    def copy_selected_link(self) -> None:
        job = self._job(self._selected)
        if job:
            self.copy_text(job.url)

    def copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._clipboard_seen = text
        self.toast.show("Link copied")

    def clear_finished(self) -> None:
        self.engine.clear_finished()
        self._selected = None
        self.queue_view.render(self.engine.jobs())

    # -- settings ----------------------------------------------------------
    def choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.settings.output_dir,
                                         title="Choose a download folder")
        if chosen:
            self.settings.output_dir = chosen
            self._settings_changed()

    def set_quality(self, label: str) -> None:
        quality = QUALITY_BY_LABEL.get(label)
        if quality and quality.id != self.settings.quality_id:
            self.settings.quality_id = quality.id
            self._settings_changed()

    def set_container(self, label: str) -> None:
        chosen = dict(zip(CONTAINER_LABELS, CONTAINERS)).get(label)
        if chosen and chosen != self.settings.container:
            self.settings.container = chosen
            self._settings_changed()

    def set_appearance(self, mode: str) -> None:
        if mode == self.settings.appearance:
            return
        self.settings.appearance = mode
        ctk.set_appearance_mode(mode)
        self._settings_changed()

    def clear_history(self) -> None:
        if not self.history.entries():
            return
        if messagebox.askyesno(
                "Clear history",
                "Remove every recorded download from the history list?\n"
                "Downloaded files are not touched.", parent=self):
            self.history.clear()
            self.history_view.render(self.history.entries())
            self.toast.show("History cleared")

    def open_config_folder(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        reveal(str(CONFIG_DIR))

    def show_about(self) -> None:
        AboutDialog(self, VERSION, str(PROJECT_ROOT))

    def _settings_changed(self) -> None:
        self.settings.save()
        self.settings_view.sync(self.settings)

    # -- engine events -----------------------------------------------------
    def _enqueue_event(self, name: str, payload) -> None:
        """Called on the worker thread — hand off to the Tk loop."""
        self._events.put((name, payload))

    def _pump(self) -> None:
        structural = False
        while True:
            try:
                name, payload = self._events.get_nowait()
            except queue.Empty:
                break

            if name == "job":
                job: Job = payload
                if job.status.is_final and job.id not in self._recorded:
                    self._recorded.add(job.id)
                    if job.status is Status.DONE:
                        self.history.add(job)
                        self.toast.show(f"Finished · {job.display_title}",
                                        t.SUCCESS)
                    elif job.status is Status.FAILED:
                        self.history.add(job)
                        self.toast.show(f"Failed · {job.display_title}",
                                        t.DANGER)
                    structural = True
                if self.queue_view.has_row(job.id):
                    self.queue_view.update_job(job)
                else:
                    structural = True
            elif name == "log":
                _job_id, line = payload
                self.log.append(line)
            elif name == "ffmpeg":
                message, _percent = payload
                self.status.set_state(message, t.WARN)
                self.settings_view.set_ffmpeg_status(message)
                self.log.append(message)
            elif name == "idle":
                structural = True

        if structural:
            self.queue_view.render(self.engine.jobs())
            if self._current_view == "history":
                self.history_view.render(self.history.entries())

        self._update_status()
        self.after(120, self._pump)

    def _update_status(self) -> None:
        jobs = self.engine.jobs()
        active = [j for j in jobs if not j.status.is_final]
        self.sidebar.set_queue_count(len(active))

        done = sum(1 for j in jobs if j.status is Status.DONE)
        failed = sum(1 for j in jobs if j.status is Status.FAILED)
        speed = sum(j.speed for j in active if j.status is Status.DOWNLOADING)
        totals = [f"{len(jobs)} in list"]
        if done:
            totals.append(f"{done} done")
        if failed:
            totals.append(f"{failed} failed")
        if speed:
            totals.append(human_speed(speed))
        self.status.set_totals("   ·   ".join(totals))

        if not active:
            self._set_title_progress(None)
            if failed:
                self.status.set_state("Finished with errors — see activity log",
                                      t.DANGER)
            else:
                self.status.set_state("Ready", t.SUCCESS)
            return

        running = next((j for j in active if j.status is not Status.QUEUED), None)
        waiting = len(active) - (1 if running else 0)
        if running is None:
            self._set_title_progress(None)
            self.status.set_state(f"{len(active)} waiting in queue", t.ACCENT)
            return

        if running.status is Status.DOWNLOADING:
            text = f"{running.percent * 100:.0f}%  ·  {running.display_title}"
            self._set_title_progress(running.percent)
        else:
            text = f"{running.status.value}  ·  {running.display_title}"
            self._set_title_progress(None)
        if waiting:
            text += f"   ·   {waiting} waiting"
        self.status.set_state(text, t.ACCENT)

    def _set_title_progress(self, fraction: float | None) -> None:
        """Mirror progress in the title, the way download managers do."""
        suffix = f"{fraction * 100:.0f}% · " if fraction is not None else ""
        if suffix != self._title_suffix:
            self._title_suffix = suffix
            self.title(f"{suffix}{APP_TITLE}")

    # -- shutdown ----------------------------------------------------------
    def _on_close(self) -> None:
        active = [j for j in self.engine.jobs() if not j.status.is_final]
        if active and not messagebox.askyesno(
                "Quit", f"{len(active)} download(s) are still running.\n"
                        "Quit and stop them?", parent=self):
            return
        self._remember_geometry()
        self.settings.save()
        self.history.save()
        self.engine.shutdown()
        self.destroy()


def run() -> None:
    App().mainloop()
