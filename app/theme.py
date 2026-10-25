"""Design tokens for the UI.

Colours are CustomTkinter tuple colours: (light mode, dark mode). Keeping every
colour here means a widget never hard-codes a hex value, so the whole app can be
retuned from one file and both appearance modes stay in sync.
"""

from __future__ import annotations

import customtkinter as ctk

# ── Surfaces ────────────────────────────────────────────────────────────────
BG = ("#EFF1F4", "#0B0C10")           # window background, behind every card
SIDEBAR = ("#FFFFFF", "#101217")      # navigation rail
SURFACE = ("#FFFFFF", "#15171D")      # cards
SURFACE_RAISED = ("#FFFFFF", "#1A1D24")  # cards that sit on top of cards
SURFACE_SUNKEN = ("#F1F3F6", "#101217")  # inputs, wells
HOVER = ("#F1F3F6", "#1F232B")
BORDER = ("#E4E7EC", "#23262F")
BORDER_STRONG = ("#D3D8E0", "#2F333E")
TRACK = ("#E6E9EF", "#23262F")

# ── Text ────────────────────────────────────────────────────────────────────
TEXT = ("#13151A", "#EEF0F4")
TEXT_DIM = ("#5A6170", "#8E96A6")
TEXT_FAINT = ("#878E9B", "#606876")
TEXT_ON_ACCENT = "#FFFFFF"

# ── Accent & semantics ──────────────────────────────────────────────────────
ACCENT = ("#2F6BFF", "#4C82FF")
ACCENT_HOVER = ("#2457DB", "#6B98FF")
ACCENT_SOFT = ("#E9F0FF", "#18233C")

SUCCESS = ("#0E8A57", "#3CC68E")
SUCCESS_SOFT = ("#E3F5EC", "#102A20")

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
SELECTED = ("#E9F0FF", "#1B2742")
SELECTED_BORDER = ("#BFD3FF", "#2C3B5E")
ROW_ALT = ("#FAFBFC", "#131519")

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
