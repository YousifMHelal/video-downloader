"""Generate the application icon.

Draws the same mark the app shows in its sidebar — a rounded accent tile with a
download arrow — and writes a multi-resolution .ico plus a PNG for other uses.

    python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)

TOP = (108, 150, 255, 255)      # lighter accent, top of the gradient
BOTTOM = (38, 92, 240, 255)     # deeper accent, bottom
GLYPH = (255, 255, 255, 255)

CANVAS = 1024  # drawn large, then downsampled for crisp edges


def gradient_tile(size: int, radius_ratio: float = 0.23) -> Image.Image:
    """Rounded square filled with a vertical accent gradient."""
    gradient = Image.new("RGBA", (1, size))
    for y in range(size):
        blend = y / max(1, size - 1)
        gradient.putpixel((0, y), tuple(
            round(TOP[i] + (BOTTOM[i] - TOP[i]) * blend) for i in range(4)))
    gradient = gradient.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255)

    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile.paste(gradient, (0, 0), mask)
    return tile


def draw_arrow(image: Image.Image) -> None:
    """A download arrow: shaft, head, and the tray line beneath it."""
    size = image.width
    draw = ImageDraw.Draw(image)
    cx = size / 2
    unit = size / 100

    shaft_w = 11 * unit
    shaft_top = 22 * unit
    shaft_bottom = 52 * unit
    draw.rounded_rectangle(
        (cx - shaft_w / 2, shaft_top, cx + shaft_w / 2, shaft_bottom),
        radius=shaft_w / 2, fill=GLYPH)

    head_half = 21 * unit
    draw.polygon([(cx - head_half, 47 * unit),
                  (cx + head_half, 47 * unit),
                  (cx, 72 * unit)], fill=GLYPH)

    tray_w = 46 * unit
    tray_h = 10 * unit
    draw.rounded_rectangle(
        (cx - tray_w / 2, 78 * unit, cx + tray_w / 2, 78 * unit + tray_h),
        radius=tray_h / 2, fill=GLYPH)


def build() -> Path:
    master = gradient_tile(CANVAS)
    draw_arrow(master)

    ASSETS.mkdir(parents=True, exist_ok=True)
    png_path = ASSETS / "icon.png"
    ico_path = ASSETS / "icon.ico"

    master.resize((512, 512), Image.LANCZOS).save(png_path)
    master.save(ico_path, format="ICO",
                sizes=[(size, size) for size in SIZES])
    return ico_path


if __name__ == "__main__":
    print(f"wrote {build()}")
