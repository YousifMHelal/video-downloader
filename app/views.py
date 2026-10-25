"""The three screens: Queue, History, Settings."""

from __future__ import annotations

from typing import Protocol

import customtkinter as ctk

from . import theme as t
from .core import (CONTAINER_LABELS, CONTAINERS, QUALITY_BY_ID, QUALITY_LABELS,
                   Job, Status, human_eta, human_size, human_speed)
from .store import HistoryEntry, relative_time
from .table import Action, Actions, Badge, CanvasTable, Progress, Text, Title
from .widgets import (STATUS_TONE, Card, SearchField, Toolbar, danger_button,
                      divider, elide, fit_text, hint_label, icon_button,
                      link_button, option_menu, popup_menu, primary_button,
                      reveal, scroll_area, secondary_button, value_box)


class Controller(Protocol):
    """What a view is allowed to ask of the application."""

    def open_add_dialog(self, url: str = "") -> None: ...
    def cancel_job(self, job_id: str) -> None: ...
    def forget_job(self, job_id: str) -> None: ...
    def row_action(self, job_id: str) -> None: ...
    def select_job(self, job_id: str | None) -> None: ...
    def clear_finished(self) -> None: ...
    def copy_text(self, text: str) -> None: ...
    def choose_folder(self) -> None: ...
    def set_quality(self, label: str) -> None: ...
    def set_container(self, label: str) -> None: ...
    def set_appearance(self, mode: str) -> None: ...
    def clear_history(self) -> None: ...
    def requeue(self, entry: HistoryEntry) -> None: ...
    def open_config_folder(self) -> None: ...


# ── Queue ───────────────────────────────────────────────────────────────────
# Every column is a fixed width and the trailing spacer takes the slack.
JOB_COLUMNS = (
    ("name", "Name", 250, 0),
    ("format", "Format", 78, 0),
    ("size", "Size", 58, 0),
    ("progress", "Progress", 110, 0),
    ("speed", "Speed", 60, 0),
    ("eta", "ETA", 42, 0),
    ("status", "Status", 92, 0),
    ("actions", "", 26, 0),
    ("spacer", "", 0, 1),
)


def recipe_label(quality_id: str, container: str) -> str:
    quality = QUALITY_BY_ID.get(quality_id)
    if quality is None:
        return "—"
    label = "Best" if quality.id == "best" else quality.label
    return label if quality.audio_only else f"{label} · {container.upper()}"


def job_cells(job: Job) -> list:
    tone, background = STATUS_TONE.get(job.status,
                                       (t.TEXT_FAINT, t.SURFACE_SUNKEN))
    suffix = (f"  · {job.item_count} items"
              if job.is_playlist and job.item_count else "")

    if job.status in (Status.PROBING, Status.PROCESSING):
        progress = Progress(None, tone)
    else:
        value = 1.0 if job.status is Status.DONE else job.percent
        progress = Progress(value, tone, f"{value * 100:.0f}%"
                            if value or job.status.is_final else "")

    downloading = job.status is Status.DOWNLOADING
    status = job.status.value
    if downloading and job.is_playlist and job.item_count:
        status = f"{job.item_index or 1}/{job.item_count}"

    return [
        Title(job.display_title, tone, suffix),
        Text(recipe_label(job.quality_id, job.container)),
        Text(human_size(job.total) if job.total else "—"),
        progress,
        Text(human_speed(job.speed) if downloading else "—"),
        Text(human_eta(job.eta) if downloading else "—"),
        Badge(status, tone, background),
        Actions((Action("✕", "row",
                        t.HOVER if job.status.is_final else t.DANGER_SOFT),)),
        None,
    ]


class DetailsPane(Card):
    """Facts about the selected row, plus the actions that apply to it."""

    FIELDS = (("link", "Link"), ("folder", "Saving to"),
              ("recipe", "Format"), ("state", "State"))

    def __init__(self, master, controller: Controller):
        super().__init__(master)
        self.controller = controller
        self.job: Job | None = None
        self.grid_columnconfigure(1, weight=1)
        fonts = t.fonts()

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=t.LG,
                  pady=(t.MD, t.SM))
        head.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(head, text="", font=fonts.body_strong,
                                        text_color=t.TEXT, anchor="w",
                                        wraplength=520, justify="left")
        self.title_label.grid(row=0, column=0, sticky="ew")
        icon_button(head, "✕", lambda: controller.select_job(None)).grid(
            row=0, column=1)

        self.values: dict[str, ctk.CTkLabel] = {}
        for index, (key, label) in enumerate(self.FIELDS, start=1):
            ctk.CTkLabel(self, text=label, font=fonts.small,
                         text_color=t.TEXT_FAINT, anchor="w", width=78).grid(
                row=index, column=0, sticky="w", padx=(t.LG, t.SM), pady=1)
            # A long path must wrap, never widen: Tk grid clips a container
            # that is smaller than what its children ask for.
            value = ctk.CTkLabel(self, text="", font=fonts.small,
                                 text_color=t.TEXT_DIM, anchor="w",
                                 justify="left", wraplength=480)
            value.grid(row=index, column=1, sticky="ew", padx=(0, t.LG), pady=1)
            self.values[key] = value

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=len(self.FIELDS) + 1, column=0, columnspan=2,
                     sticky="w", padx=t.LG - 4, pady=(t.SM, t.MD))
        link_button(actions, "Open folder", self._open).grid(row=0, column=0)
        link_button(actions, "Copy link", self._copy).grid(row=0, column=1,
                                                            padx=(t.MD, 0))
        self.action_link = link_button(actions, "Cancel", self._action)
        self.action_link.grid(row=0, column=2, padx=(t.MD, 0))

    def _open(self) -> None:
        if self.job:
            reveal(self.job.dest_dir)

    def _copy(self) -> None:
        if self.job:
            self.controller.copy_text(self.job.url)

    def _action(self) -> None:
        if self.job:
            self.controller.row_action(self.job.id)

    def show(self, job: Job) -> None:
        self.job = job
        self.title_label.configure(text=job.display_title)
        self.values["link"].configure(text=elide(job.url, 96))
        self.values["folder"].configure(text=elide(job.dest_dir or "—", 96))
        self.values["recipe"].configure(text=job.recipe)

        state = job.status.value
        if job.is_playlist and job.item_count:
            state += f" · playlist, {job.item_count} items"
        if job.message:
            state += f" · {job.message}"
        self.values["state"].configure(text=state)
        self.action_link.configure(
            text="Remove" if job.status.is_final else "Cancel")


class QueueView(ctk.CTkFrame):
    def __init__(self, master, controller: Controller, settings):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._filter = ""
        self._jobs: list[Job] = []

        # Toolbar ----------------------------------------------------------
        bar = Toolbar(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, t.MD))
        bar.add(primary_button(bar, "+  Add download",
                               lambda: controller.open_add_dialog(), width=142))
        bar.add_separator()
        self.cancel_button = bar.add(
            secondary_button(bar, "Cancel", self._cancel_selected, width=86))
        self.open_button = bar.add(
            secondary_button(bar, "Open folder", self._open_selected, width=108))
        self.remove_button = bar.add(
            secondary_button(bar, "Remove", self._remove_selected, width=86))
        bar.add_separator()
        bar.add(secondary_button(bar, "Clear finished",
                                 controller.clear_finished, width=118))
        bar.add_spacer()
        self.search = SearchField(bar, self._on_filter, "Filter downloads…")
        bar.add(self.search, pad=0, sticky="e")

        # Table ------------------------------------------------------------
        self.table = CanvasTable(
            self, JOB_COLUMNS, on_select=controller.select_job,
            on_menu=self._context_menu,
            on_action=lambda job_id, _name: controller.row_action(job_id))
        self.table.grid(row=1, column=0, sticky="nsew")
        self.table.set_empty(
            "↓", "Nothing in the queue",
            "Add a link to start downloading. Playlists are detected "
            "automatically and saved to their own folder.",
            "Add download", lambda: controller.open_add_dialog())

        # Details ----------------------------------------------------------
        self.details = DetailsPane(self, controller)

        self._menu = popup_menu(self)
        self._menu_job: str | None = None
        self._menu.add_command(label="Open folder", command=self._menu_open)
        self._menu.add_command(label="Copy link", command=self._menu_copy)
        self._menu.add_separator()
        self._menu.add_command(label="Cancel", command=self._menu_cancel)
        self._menu.add_command(label="Remove from list",
                               command=self._menu_remove)

        self.sync_selection(None)

    # -- toolbar actions ---------------------------------------------------
    def _selected_job(self) -> Job | None:
        job_id = self.table.selected
        return next((j for j in self._jobs if j.id == job_id), None)

    def _cancel_selected(self) -> None:
        job = self._selected_job()
        if job and not job.status.is_final:
            self.controller.cancel_job(job.id)

    def _remove_selected(self) -> None:
        job = self._selected_job()
        if job and job.status.is_final:
            self.controller.forget_job(job.id)

    def _open_selected(self) -> None:
        job = self._selected_job()
        if job:
            reveal(job.dest_dir)

    def _on_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self.render(self._jobs)

    # -- context menu ------------------------------------------------------
    def _context_menu(self, job_id: str, event) -> None:
        self.controller.select_job(job_id)
        self._menu_job = job_id
        job = next((j for j in self._jobs if j.id == job_id), None)
        if job is not None:
            final = job.status.is_final
            self._menu.entryconfigure("Cancel",
                                      state="disabled" if final else "normal")
            self._menu.entryconfigure("Remove from list",
                                      state="normal" if final else "disabled")
            self._menu.entryconfigure(
                "Open folder", state="normal" if job.dest_dir else "disabled")
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _menu_target(self) -> Job | None:
        return next((j for j in self._jobs if j.id == self._menu_job), None)

    def _menu_open(self) -> None:
        job = self._menu_target()
        if job:
            reveal(job.dest_dir)

    def _menu_copy(self) -> None:
        job = self._menu_target()
        if job:
            self.controller.copy_text(job.url)

    def _menu_cancel(self) -> None:
        if self._menu_job:
            self.controller.cancel_job(self._menu_job)

    def _menu_remove(self) -> None:
        if self._menu_job:
            self.controller.forget_job(self._menu_job)

    # -- rendering ---------------------------------------------------------
    def _visible(self, jobs: list[Job]) -> list[Job]:
        if not self._filter:
            return jobs
        needle = self._filter
        return [j for j in jobs
                if needle in j.display_title.lower() or needle in j.url.lower()]

    def render(self, jobs: list[Job]) -> None:
        self._jobs = jobs
        self.table.set_rows([(job.id, job_cells(job))
                             for job in self._visible(jobs)])
        self.sync_selection(self.table.selected)

    def update_job(self, job: Job) -> None:
        for index, existing in enumerate(self._jobs):
            if existing.id == job.id:
                self._jobs[index] = job
                break
        self.table.update_row(job.id, job_cells(job))
        if self.table.selected == job.id:
            self.details.show(job)

    def has_row(self, job_id: str) -> bool:
        return self.table.has_row(job_id)

    def sync_selection(self, job_id: str | None) -> None:
        self.table.select(job_id)
        job = self._selected_job()
        if job is None:
            self.details.grid_remove()
            for button in (self.cancel_button, self.open_button,
                           self.remove_button):
                button.configure(state="disabled")
            return

        self.details.show(job)
        self.details.grid(row=2, column=0, sticky="ew", pady=(t.MD, 0))
        self.cancel_button.configure(
            state="disabled" if job.status.is_final else "normal")
        self.remove_button.configure(
            state="normal" if job.status.is_final else "disabled")
        self.open_button.configure(
            state="normal" if job.dest_dir else "disabled")


# ── History ─────────────────────────────────────────────────────────────────
HISTORY_COLUMNS = (
    ("name", "Name", 250, 0),
    ("when", "When", 86, 0),
    ("format", "Format", 96, 0),
    ("size", "Size", 58, 0),
    ("status", "Status", 80, 0),
    ("actions", "", 58, 0),
    ("spacer", "", 0, 1),
)


def history_cells(record: HistoryEntry) -> list:
    status = Status(record.status) if record.status in {
        s.value for s in Status} else Status.DONE
    tone, background = STATUS_TONE[status]
    return [
        Title(record.title, t.SUCCESS if status is Status.DONE else t.DANGER),
        Text(relative_time(record.finished_at)),
        Text(recipe_label(record.quality_id, record.container)),
        Text(human_size(record.bytes) if record.bytes else "—"),
        Badge(status.value, tone, background),
        Actions((Action("↻", "requeue"), Action("⌸", "reveal"))),
        None,
    ]


class HistoryView(ctk.CTkFrame):
    def __init__(self, master, controller: Controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._records: list[HistoryEntry] = []
        self._shown: dict[str, HistoryEntry] = {}
        self._filter = ""

        bar = Toolbar(self)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, t.MD))
        self.count_label = bar.add(
            ctk.CTkLabel(bar, text="", font=t.fonts().small,
                         text_color=t.TEXT_FAINT, anchor="w"), pad=t.MD)
        bar.add_spacer()
        self.search = SearchField(bar, self._on_filter, "Filter history…")
        bar.add(self.search, pad=t.SM, sticky="e")
        self.clear_button = bar.add(
            danger_button(bar, "Clear history", controller.clear_history,
                          width=116), pad=0, sticky="e")

        self.table = CanvasTable(self, HISTORY_COLUMNS,
                                 on_action=self._row_action)
        self.table.grid(row=1, column=0, sticky="nsew")
        self.table.set_empty(
            "◴", "No history yet",
            "Finished downloads are recorded here so you can reopen their "
            "folder or fetch them again later.")

    def _on_filter(self, text: str) -> None:
        self._filter = text.strip().lower()
        self.render(self._records)

    def _row_action(self, key: str, name: str) -> None:
        record = self._shown.get(key)
        if record is None:
            return
        if name == "requeue":
            self.controller.requeue(record)
        elif name == "reveal":
            reveal(record.dest_dir)

    def render(self, records: list[HistoryEntry]) -> None:
        self._records = records
        total = len(records)
        self.count_label.configure(
            text=f"{total} download{'s' if total != 1 else ''} recorded")
        self.clear_button.configure(state="normal" if total else "disabled")

        visible = [r for r in records
                   if not self._filter
                   or self._filter in r.title.lower()
                   or self._filter in r.url.lower()]
        # Entries carry no id, and the same link can appear more than once.
        self._shown = {str(index): record
                       for index, record in enumerate(visible)}
        self.table.set_rows([(key, history_cells(record))
                             for key, record in self._shown.items()])


# ── Settings ────────────────────────────────────────────────────────────────
class SettingsGroup(Card):
    """Titled group of preference rows, like a native settings pane."""

    def __init__(self, master, title: str, subtitle: str):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self._row = 2
        ctk.CTkLabel(self, text=title, font=t.fonts().title, text_color=t.TEXT,
                     anchor="w").grid(row=0, column=0, columnspan=2,
                                      sticky="ew", padx=t.LG, pady=(t.MD, 0))
        hint_label(self, subtitle).grid(row=1, column=0, columnspan=2,
                                        sticky="ew", padx=t.LG, pady=(2, t.SM))

    def add_row(self, label: str, description: str, control) -> None:
        """Label and description on the left, ``control`` on the right.

        ``control`` must be a child of this group. Everything is gridded
        straight into the card: every extra frame is more native windows
        for Tk to repaint on each resize.
        """
        if self._row > 2:
            divider(self).grid(row=self._row, column=0, columnspan=2,
                               sticky="ew", padx=t.LG)
            self._row += 1

        top = self._row
        self._row += 2
        ctk.CTkLabel(self, text=label, font=t.fonts().body_strong,
                     text_color=t.TEXT, anchor="w").grid(
            row=top, column=0, sticky="sw", padx=(t.LG, 0), pady=(t.MD, 0))
        hint_label(self, description).grid(
            row=top + 1, column=0, sticky="nw", padx=(t.LG, 0), pady=(0, t.MD))
        control.grid(row=top, column=1, rowspan=2, sticky="e",
                     padx=t.LG, pady=t.MD)


class SettingsView(ctk.CTkFrame):
    FOLDER_W = 280

    def __init__(self, master, controller: Controller, settings):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        area = scroll_area(self)
        area.grid(row=0, column=0, sticky="nsew")

        downloads = SettingsGroup(area, "Downloads",
                                  "Defaults for every new item in the queue.")
        downloads.grid(row=0, column=0, sticky="ew", pady=(0, t.MD))

        folder_control = ctk.CTkFrame(downloads, fg_color="transparent")
        self.folder_value = value_box(folder_control)
        self.folder_value.configure(text_color=t.TEXT, width=self.FOLDER_W)
        self.folder_value.grid(row=0, column=0, sticky="e")
        secondary_button(folder_control, "Browse…", controller.choose_folder,
                         width=92).grid(row=0, column=1, padx=(t.SM, 0))
        downloads.add_row("Save downloads to",
                          "Playlists get their own folder inside this one.",
                          folder_control)

        self.quality_var = ctk.StringVar()
        downloads.add_row(
            "Quality", "Picked per download; audio only produces MP3.",
            option_menu(downloads, QUALITY_LABELS, controller.set_quality,
                        self.quality_var, width=168))

        self.container_var = ctk.StringVar()
        self.container_menu = option_menu(downloads, CONTAINER_LABELS,
                                          controller.set_container,
                                          self.container_var, width=112)
        downloads.add_row("Container", "The file type video downloads merge to.",
                          self.container_menu)

        look = SettingsGroup(area, "Appearance",
                             "Follow Windows or pin the window to one theme.")
        look.grid(row=1, column=0, sticky="ew", pady=(0, t.MD))
        self.appearance = ctk.CTkSegmentedButton(
            look, values=["System", "Light", "Dark"],
            command=lambda value: controller.set_appearance(value.lower()),
            height=t.H_CTRL, corner_radius=t.R_CTRL,
            selected_color=t.ACCENT, selected_hover_color=t.ACCENT_HOVER,
            unselected_color=t.SURFACE_SUNKEN, unselected_hover_color=t.HOVER,
            text_color=t.TEXT, font=t.fonts().body)
        look.add_row("Theme", "Changes apply immediately.", self.appearance)

        tools = SettingsGroup(area, "Tools and data",
                              "Where the app keeps the pieces it needs.")
        tools.grid(row=2, column=0, sticky="ew")
        self.ffmpeg_label = ctk.CTkLabel(tools, text="", font=t.fonts().small,
                                         text_color=t.TEXT_DIM, anchor="e",
                                         wraplength=320, justify="right")
        tools.add_row("ffmpeg",
                      "Merges video and audio; installed automatically.",
                      self.ffmpeg_label)

        data_control = ctk.CTkFrame(tools, fg_color="transparent")
        secondary_button(data_control, "Open folder",
                         controller.open_config_folder, width=116,
                         height=t.H_BUTTON_SM).grid(row=0, column=0)
        danger_button(data_control, "Clear history", controller.clear_history,
                      width=116, height=t.H_BUTTON_SM).grid(row=0, column=1,
                                                            padx=(t.SM, 0))
        tools.add_row("Settings and history",
                      "Stored as JSON beside the app.", data_control)

        self.sync(settings)

    def set_ffmpeg_status(self, text: str) -> None:
        self.ffmpeg_label.configure(text=text)

    def sync(self, settings) -> None:
        quality = QUALITY_BY_ID[settings.quality_id]
        # Keep the end of the path: the folder name is the part that matters.
        folder = fit_text(settings.output_dir, t.fonts().body,
                          self.FOLDER_W - 2 * t.MD, keep_end=True)
        self.folder_value.configure(text=f"  {folder}")
        self.quality_var.set(quality.label)
        self.container_var.set(dict(zip(CONTAINERS, CONTAINER_LABELS))[
            settings.container])
        self.container_menu.configure(
            state="disabled" if quality.audio_only else "normal")
        self.appearance.set(settings.appearance.capitalize())
