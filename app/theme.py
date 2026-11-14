"""Design tokens for the UI.

Colours are CustomTkinter tuple colours: (light mode, dark mode). Keeping every
colour here means a widget never hard-codes a hex value, so the whole app can be
retuned from one file and both appearance modes stay in sync.
"""

from __future__ import annotations

import customtkinter as ctk

# Palette: Stealth Black (main, 60%), Titanium Grey (second, 30%),
# Venom Green #39FF7A (accent, 10%). Light mode uses a deeper green, since
# #39FF7A on white is unreadable as text.

# ── Surfaces ────────────────────────────────────────────────────────────────
BG = ("#E9EBED", "#0B0C0D")           # window background, behind every card
SIDEBAR = ("#F7F8F9", "#101113")      # navigation rail
SURFACE = ("#FFFFFF", "#141517")      # cards
SURFACE_RAISED = ("#FFFFFF", "#1A1C1F")  # cards that sit on top of cards
SURFACE_SUNKEN = ("#EEF0F2", "#0F1011")  # inputs, wells
HOVER = ("#E6E8EB", "#1F2124")
BORDER = ("#DCDFE3", "#25282C")
BORDER_STRONG = ("#C7CBD0", "#33373C")
TRACK = ("#DFE2E6", "#25282C")

# ── Text ────────────────────────────────────────────────────────────────────
TEXT = ("#0E0F11", "#ECEEF0")
TEXT_DIM = ("#565B62", "#9AA0A6")     # titanium grey
TEXT_FAINT = ("#868B92", "#666B71")
TEXT_ON_ACCENT = ("#FFFFFF", "#06120A")  # dark text: white on venom is unreadable

# ── Accent & semantics ──────────────────────────────────────────────────────
ACCENT = ("#0B8A3E", "#39FF7A")       # venom green
ACCENT_HOVER = ("#097534", "#6BFF9A")
ACCENT_SOFT = ("#E1F7E9", "#10261A")

SUCCESS = ("#13784A", "#5FD38D")      # calmer than the accent, so "done" reads apart
SUCCESS_SOFT = ("#E4F4EA", "#112219")

DANGER = ("#C33327", "#F4685C")
DANGER_SOFT = ("#FBE9E7", "#301A19")
DANGER_HOVER = ("#A82A21", "#FF8178")

WARN = ("#95590A", "#E3A842")
WARN_SOFT = ("#FBF1DD", "#2C2411")

# ── Shape ───────────────────────────────────────────────────────────────────
R_CARD = 12
R_CTRL = 8
R_PILL = 20

# ── Spacing scale (4px rhythm) ──────────────────────────────────────────────
XS, SM, MD, LG, XL, XXL = 4, 8, 12, 16, 24, 32

# ── Selection (table rows) ──────────────────────────────────────────────────
SELECTED = ("#E4F7EB", "#12241A")
SELECTED_BORDER = ("#A9E5BF", "#1F4A2F")
ROW_ALT = ("#FAFBFB", "#121315")

# ── Sizing ──────────────────────────────────────────────────────────────────
SIDEBAR_W = 206
HEADER_H = 64
TOOLBAR_H = 44
ROW_H = 42
TABLE_HEAD_H = 28
STATUS_H = 28
H_CTRL = 34
H_BUTTON = 34
H_BUTTON_SM = 28
H_NAV = 34

_FAMILY = "Segoe UI"
_FAMILY_MONO = "Consolas"


class Fonts:
    """Typographic scale. Must be built after the Tk root exists."""

    def __init__(self) -> None:
        self.display = ctk.CTkFont(family=_FAMILY, size=20, weight="bold")
        self.title = ctk.CTkFont(family=_FAMILY, size=15, weight="bold")
        self.subtitle = ctk.CTkFont(family=_FAMILY, size=14, weight="bold")
        self.body = ctk.CTkFont(family=_FAMILY, size=13)
        self.body_strong = ctk.CTkFont(family=_FAMILY, size=13, weight="bold")
        self.small = ctk.CTkFont(family=_FAMILY, size=12)
        self.small_strong = ctk.CTkFont(family=_FAMILY, size=12, weight="bold")
        self.label = ctk.CTkFont(family=_FAMILY, size=11, weight="bold")
        self.mono = ctk.CTkFont(family=_FAMILY_MONO, size=12)
        self.glyph = ctk.CTkFont(family=_FAMILY, size=26)
        self.mark = ctk.CTkFont(family=_FAMILY, size=16, weight="bold")


_fonts: Fonts | None = None


def fonts() -> Fonts:
    """Cached font scale. Safe to call from any widget constructor."""
    global _fonts
    if _fonts is None:
        _fonts = Fonts()
    return _fonts
