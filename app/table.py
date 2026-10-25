"""A table drawn on a canvas.

Every CustomTkinter widget is two or three native windows, and Tk repaints
each of them whenever the window resizes or a page is shown. A table built
from a frame per row and a widget per cell therefore got slower with every
row: 22 history entries took over a second to show. Here the header, the rows
and the empty state are canvas items instead, which cost next to nothing to
redraw however many there are.
"""

from __future__ import annotations

import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Callable, Sequence, Union

import customtkinter as ctk

from . import theme as t
from .widgets import Card, fit_text

Color = Union[str, tuple[str, str]]
Column = tuple[str, str, int, int]  # key, heading, width, weight

ROW_PITCH = t.ROW_H + 2  # rows sit 1px apart above and below
ROW_INSET = t.XS         # rows stop short of the canvas edges
ACTION = 24              # side of a row action's hit box
BADGE_H = 20
BAR_H = 5
PERCENT_W = 30
SPIN_MS = 30


# ── Cells ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Text:
    text: str
    color: Color = t.TEXT_DIM
    font: str = "small"


@dataclass(frozen=True)
class Title:
    """Primary text led by a status dot; the suffix is never elided."""

    text: str
    tone: Color
    suffix: str = ""


@dataclass(frozen=True)
class Progress:
    value: float | None  # None sweeps back and forth: no length known yet
    tone: Color
    label: str = ""


@dataclass(frozen=True)
class Badge:
    text: str
    tone: Color
    background: Color


@dataclass(frozen=True)
class Action:
    glyph: str
    name: str
    hover: Color = t.HOVER


@dataclass(frozen=True)
class Actions:
    items: tuple[Action, ...]


Cell = Union[Text, Title, Progress, Badge, Actions, None]
Row = tuple[str, Sequence[Cell]]


class CanvasTable(Card):
    """Header, scrolling rows and an empty state, with hover and selection.

    Rows are identified by a string key; callbacks receive that key.
    """

    def __init__(self, master, columns: Sequence[Column],
                 on_select: Callable[[str], None] | None = None,
                 on_menu: Callable[[str, object], None] | None = None,
                 on_action: Callable[[str, str], None] | None = None):
        self._ready = False  # scaling and theme hooks fire during setup
        super().__init__(master)
        self._columns = self._place_columns(columns)
        self._on_select = on_select
        self._on_menu = on_menu
        self._on_action = on_action

        self._keys: list[str] = []
        self._cells: dict[str, Sequence[Cell]] = {}
        self._index: dict[str, int] = {}
        self._hover: tuple[str | None, Action | None] = (None, None)
        self._spinners: dict[str, tuple[int, float, float, float, float]] = {}
        self._spin_phase = 0.0
        self._spin_job: str | None = None
        self._empty: tuple[str, str, str, str | None, Callable | None] | None = None
        self._empty_button: tuple[float, float, float, float] | None = None
        self._empty_hover = False
        self._font_cache: dict[tuple, tkfont.Font] = {}
        self.selected: str | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.header = ctk.CTkCanvas(self, highlightthickness=0, borderwidth=0)
        self.body = ctk.CTkCanvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ctk.CTkScrollbar(
            self, command=self.body.yview, fg_color="transparent",
            button_color=t.BORDER_STRONG, button_hover_color=t.TEXT_FAINT)
        self.scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, t.XS),
                            pady=(0, t.XS))
        self.body.configure(yscrollcommand=self._on_scroll)
        self._grid_canvases()

        self.header.bind("<Configure>", lambda _e: self._draw_header())
        self.body.bind("<Configure>", lambda _e: self._on_resize())
        self.body.bind("<Motion>", self._on_motion)
        self.body.bind("<Leave>", self._on_leave)
        self.body.bind("<Button-1>", self._on_click)
        self.body.bind("<Button-3>", self._on_right_click)
        self.body.bind("<MouseWheel>", self._on_wheel)
        self.body.bind("<Button-4>", lambda _e: self.body.yview_scroll(-3, "units"))
        self.body.bind("<Button-5>", lambda _e: self.body.yview_scroll(3, "units"))

        self._ready = True
        self._redraw()

    # -- public ------------------------------------------------------------
    def set_rows(self, rows: Sequence[Row]) -> None:
        self._keys = [key for key, _cells in rows]
        self._cells = dict(rows)
        self._index = {key: index for index, key in enumerate(self._keys)}
        if self.selected not in self._index:
            self.selected = None
        if self._hover[0] not in self._index:
            self._hover = (None, None)
        self._draw_body()

    def update_row(self, key: str, cells: Sequence[Cell]) -> None:
        index = self._index.get(key)
        if index is None:
            return
        self._cells[key] = cells
        self._draw_row(index, key)
        if self._hover[0] == key:
            self._draw_highlights()
        self._sync_spinner()

    def has_row(self, key: str) -> bool:
        return key in self._index

    def select(self, key: str | None) -> None:
        self.selected = key if key in self._index else None
        self._draw_highlights()

    def set_empty(self, glyph: str, title: str, body: str,
                  action: str | None = None, command=None) -> None:
        self._empty = (glyph, title, body, action, command)
        self._draw_empty()

    # -- CustomTkinter hooks ----------------------------------------------
    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        if self._ready:
            self._redraw()

    def _set_scaling(self, new_widget_scaling, new_window_scaling):
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        if self._ready:
            self._font_cache.clear()
            self._grid_canvases()
            self._redraw()

    def destroy(self):
        if self._spin_job is not None:
            self.after_cancel(self._spin_job)
            self._spin_job = None
        super().destroy()

    # -- geometry ----------------------------------------------------------
    @staticmethod
    def _place_columns(columns: Sequence[Column]) -> list[tuple[str, int, int]]:
        """(heading, left edge, width) per column, in unscaled units."""
        placed, x = [], ROW_INSET
        for index, (_key, heading, width, _weight) in enumerate(columns):
            x += t.MD if index == 0 else t.SM
            placed.append((heading, x, width))
            x += width
        return placed

    def _grid_canvases(self) -> None:
        # Plain canvases sit outside CustomTkinter's scaling, so their
        # padding and sizes are scaled here.
        inset = round(self._px(t.XS))
        self.header.configure(height=round(self._px(t.TABLE_HEAD_H + 1 + t.XS)))
        self.header.grid(row=0, column=0, sticky="ew", padx=inset,
                         pady=(round(self._px(t.SM)), 0))
        self.body.configure(yscrollincrement=round(self._px(20)))
        self.body.grid(row=1, column=0, sticky="nsew", padx=inset,
                       pady=(0, inset))

    def _px(self, value: float) -> float:
        return value * self._get_widget_scaling()

    def _color(self, color: Color) -> str:
        return self._apply_appearance_mode(color)

    def _font(self, name: str) -> tkfont.Font:
        spec = getattr(t.fonts(), name).create_scaled_tuple(
            self._get_widget_scaling())
        font = self._font_cache.get(spec)
        if font is None:
            font = self._font_cache[spec] = tkfont.Font(root=self, font=spec)
        return font

    def _row_top(self, index: int) -> float:
        return self._px(index * ROW_PITCH + 1)

    def _action_box(self, key: str, action: Action):
        index = self._index.get(key)
        if index is None:
            return None
        for (_heading, x, _width), cell in zip(self._columns, self._cells[key]):
            if isinstance(cell, Actions) and action in cell.items:
                left = x + cell.items.index(action) * ACTION
                top = index * ROW_PITCH + 1 + (t.ROW_H - ACTION) / 2
                return (self._px(left), self._px(top),
                        self._px(left + ACTION), self._px(top + ACTION))
        return None

    def _hit(self, event) -> tuple[str | None, Action | None]:
        x, y = self.body.canvasx(event.x), self.body.canvasy(event.y)
        index = int(y // self._px(ROW_PITCH))
        if not 0 <= index < len(self._keys):
            return None, None
        key = self._keys[index]
        for cell in self._cells[key]:
            if isinstance(cell, Actions):
                for action in cell.items:
                    x0, y0, x1, y1 = self._action_box(key, action)
                    if x0 <= x < x1 and y0 <= y < y1:
                        return key, action
        return key, None

    # -- drawing -----------------------------------------------------------
    def _round_rect(self, canvas, x0, y0, x1, y1, radius, fill, tags) -> None:
        radius = int(min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
        if radius < 1:
            canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="",
                                    width=0, tags=tags)
            return
        for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius),
                       (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
            canvas.create_aa_circle(cx, cy, radius, fill=fill, tags=tags)
        canvas.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=fill,
                                outline="", width=0, tags=tags)
        canvas.create_rectangle(x0, y0 + radius, x1, y1 - radius, fill=fill,
                                outline="", width=0, tags=tags)

    def _pill(self, canvas, x0, y0, x1, y1, fill, tags) -> None:
        self._round_rect(canvas, x0, y0, x1, y1, (y1 - y0) / 2, fill, tags)

    def _redraw(self) -> None:
        background = self._color(self.cget("fg_color"))
        self.header.configure(bg=background)
        self.body.configure(bg=background)
        self._draw_header()
        self._draw_body()

    def _draw_header(self) -> None:
        canvas = self.header
        canvas.delete("all")
        font, color = self._font("label"), self._color(t.TEXT_FAINT)
        middle = self._px(t.TABLE_HEAD_H / 2)
        for heading, x, _width in self._columns:
            if heading:
                canvas.create_text(self._px(x), middle, text=heading.upper(),
                                   anchor="w", font=font, fill=color)
        y = round(self._px(t.TABLE_HEAD_H))
        canvas.create_rectangle(self._px(t.XS), y,
                                canvas.winfo_width() - self._px(t.XS), y + 1,
                                fill=self._color(t.BORDER), outline="", width=0)

    def _draw_body(self) -> None:
        self.body.delete("all")
        self._spinners.clear()
        for index, key in enumerate(self._keys):
            self._draw_row(index, key)
        self._draw_empty()
        self._draw_highlights()
        self._update_region()
        self._sync_spinner()

    def _draw_row(self, index: int, key: str) -> None:
        canvas, tag = self.body, f"row:{key}"
        canvas.delete(tag)
        self._spinners.pop(key, None)
        middle = self._row_top(index) + self._px(t.ROW_H / 2)
        for (_heading, x, width), cell in zip(self._columns, self._cells[key]):
            left, room = self._px(x), self._px(width)
            if isinstance(cell, Text):
                font = self._font(cell.font)
                canvas.create_text(left, middle, anchor="w", font=font,
                                   text=fit_text(cell.text, font, room),
                                   fill=self._color(cell.color), tags=tag)
            elif isinstance(cell, Title):
                self._draw_title(canvas, cell, left, room, middle, tag)
            elif isinstance(cell, Progress):
                self._draw_progress(canvas, key, cell, left, room, middle, tag)
            elif isinstance(cell, Badge):
                self._draw_badge(canvas, cell, left, room, middle, tag)
            elif isinstance(cell, Actions):
                font, color = self._font("body_strong"), self._color(t.TEXT_FAINT)
                for offset, action in enumerate(cell.items):
                    canvas.create_text(
                        left + self._px((offset + 0.5) * ACTION), middle,
                        text=action.glyph, font=font, fill=color, tags=tag)

    def _draw_title(self, canvas, cell: Title, left, room, middle, tag) -> None:
        radius = round(self._px(4))
        canvas.create_aa_circle(left + radius, middle, radius,
                                fill=self._color(cell.tone), tags=tag)
        indent = self._px(8 + t.SM)
        font = self._font("body")
        text = fit_text(cell.text, font,
                        room - indent - font.measure(cell.suffix)) + cell.suffix
        canvas.create_text(left + indent, middle, text=text, anchor="w",
                           font=font, fill=self._color(t.TEXT), tags=tag)

    def _draw_progress(self, canvas, key, cell: Progress, left, room, middle,
                       tag) -> None:
        right = left + room - self._px(PERCENT_W + t.XS)
        height = self._px(BAR_H)
        top, bottom = middle - height / 2, middle + height / 2
        tone = self._color(cell.tone)
        self._pill(canvas, left, top, right, bottom, self._color(t.TRACK), tag)
        if cell.value is None:
            item = canvas.create_rectangle(left, top, left, bottom, fill=tone,
                                           outline="", width=0, tags=tag)
            self._spinners[key] = (item, left, right, top, bottom)
        elif cell.value > 0:
            filled = left + max(height, (right - left) * min(1.0, cell.value))
            self._pill(canvas, left, top, filled, bottom, tone, tag)
        if cell.label:
            canvas.create_text(left + room, middle, text=cell.label, anchor="e",
                               font=self._font("small"),
                               fill=self._color(t.TEXT_DIM), tags=tag)

    def _draw_badge(self, canvas, cell: Badge, left, room, middle, tag) -> None:
        font, pad = self._font("small_strong"), self._px(t.SM)
        text = fit_text(cell.text, font, room - 2 * pad)
        width = font.measure(text) + 2 * pad
        height = self._px(BADGE_H)
        self._pill(canvas, left, middle - height / 2, left + width,
                   middle + height / 2, self._color(cell.background), tag)
        canvas.create_text(left + width / 2, middle, text=text, font=font,
                           fill=self._color(cell.tone), tags=tag)

    def _draw_highlights(self) -> None:
        """Selection, hover and action-hover backdrops, beneath the rows."""
        canvas = self.body
        canvas.delete("hl")
        left = self._px(ROW_INSET)
        right = canvas.winfo_width() - left
        radius = self._px(t.R_CTRL)
        hover_key, hover_action = self._hover
        backdrops = [(self.selected, t.SELECTED)]
        if hover_key != self.selected:
            backdrops.append((hover_key, t.HOVER))
        for key, color in backdrops:
            if key in self._index:
                top = self._row_top(self._index[key])
                self._round_rect(canvas, left, top, right,
                                 top + self._px(t.ROW_H), radius,
                                 self._color(color), "hl")
        if hover_key is not None and hover_action is not None:
            box = self._action_box(hover_key, hover_action)
            if box:
                self._round_rect(canvas, *box, radius,
                                 self._color(hover_action.hover), "hl")
        if canvas.find_withtag("hl"):
            canvas.tag_lower("hl")

    def _draw_empty(self) -> None:
        canvas = self.body
        canvas.delete("empty")
        self._empty_button = None
        if self._keys or self._empty is None:
            return
        glyph, title, body, action, command = self._empty
        middle = canvas.winfo_width() / 2
        y = self._px(t.XXL)

        box = self._px(52)
        self._round_rect(canvas, middle - box / 2, y, middle + box / 2, y + box,
                         self._px(16), self._color(t.SURFACE_SUNKEN), "empty")
        canvas.create_text(middle, y + box / 2, text=glyph,
                           font=self._font("glyph"),
                           fill=self._color(t.TEXT_FAINT), tags="empty")
        y += box + self._px(t.MD)

        title_font = self._font("subtitle")
        canvas.create_text(middle, y, text=title, anchor="n", font=title_font,
                           fill=self._color(t.TEXT_DIM), tags="empty")
        y += title_font.metrics("linespace") + self._px(t.XS)
        item = canvas.create_text(middle, y, text=body, anchor="n",
                                  justify="center", width=self._px(400),
                                  font=self._font("small"),
                                  fill=self._color(t.TEXT_FAINT), tags="empty")
        y = canvas.bbox(item)[3] + self._px(t.MD)

        if action and command:
            width, height = self._px(150), self._px(t.H_BUTTON)
            x0, x1, y1 = middle - width / 2, middle + width / 2, y + height
            radius, line = self._px(t.R_CTRL), max(1, round(self._px(1)))
            self._round_rect(canvas, x0, y, x1, y1, radius,
                             self._color(t.BORDER_STRONG), "empty")
            self._round_rect(canvas, x0 + line, y + line, x1 - line, y1 - line,
                             radius - line,
                             self._color(t.HOVER if self._empty_hover
                                         else t.SURFACE), "empty")
            canvas.create_text(middle, y + height / 2, text=action,
                               font=self._font("body"),
                               fill=self._color(t.TEXT), tags="empty")
            self._empty_button = (x0, y, x1, y1)

    def _update_region(self) -> None:
        canvas = self.body
        height = max(self._px(len(self._keys) * ROW_PITCH),
                     canvas.winfo_height())
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))

    # -- indeterminate progress -------------------------------------------
    def _sync_spinner(self) -> None:
        if self._spinners and self._spin_job is None:
            self._spin_job = self.after(SPIN_MS, self._spin)

    def _spin(self) -> None:
        self._spin_job = None
        self._spin_phase = (self._spin_phase + 0.015) % 1.0
        for item, x0, x1, y0, y1 in self._spinners.values():
            span = x1 - x0
            segment = span * 0.35
            head = x0 + (span + segment) * self._spin_phase
            start = min(max(x0, head - segment), x1)
            self.body.coords(item, start, y0, max(min(x1, head), start), y1)
        self._sync_spinner()

    # -- events ------------------------------------------------------------
    def _on_resize(self) -> None:
        self._update_region()
        self._draw_highlights()
        self._draw_empty()

    def _on_scroll(self, first, last) -> None:
        self.scrollbar.set(first, last)
        needed = float(first) > 0 or float(last) < 1
        if needed and not self.scrollbar.winfo_manager():
            self.scrollbar.grid()
        elif not needed and self.scrollbar.winfo_manager():
            self.scrollbar.grid_remove()

    def _set_hover(self, key: str | None, action: Action | None) -> None:
        if (key, action) != self._hover:
            self._hover = (key, action)
            self._draw_highlights()
        self._sync_cursor()

    def _sync_cursor(self) -> None:
        pointer = self._hover[1] is not None or self._empty_hover
        self.body.configure(cursor="hand2" if pointer else "")

    def _on_motion(self, event) -> None:
        if self._empty_button is not None:
            x0, y0, x1, y1 = self._empty_button
            x, y = self.body.canvasx(event.x), self.body.canvasy(event.y)
            inside = x0 <= x < x1 and y0 <= y < y1
            if inside != self._empty_hover:
                self._empty_hover = inside
                self._draw_empty()
        self._set_hover(*self._hit(event))

    def _on_leave(self, _event) -> None:
        if self._empty_hover:
            self._empty_hover = False
            self._draw_empty()
        self._set_hover(None, None)

    def _on_click(self, event) -> None:
        if self._empty_hover and self._empty and self._empty[4]:
            self._empty[4]()
            return
        key, action = self._hit(event)
        if key is None:
            return
        if action is not None:
            if self._on_action:
                self._on_action(key, action.name)
        elif self._on_select:
            self._on_select(key)

    def _on_right_click(self, event) -> None:
        key, _action = self._hit(event)
        if key is not None and self._on_menu:
            self._on_menu(key, event)

    def _on_wheel(self, event) -> None:
        steps = -round(event.delta / 40)
        if steps:
            self.body.yview_scroll(steps, "units")
            self._set_hover(*self._hit(event))
