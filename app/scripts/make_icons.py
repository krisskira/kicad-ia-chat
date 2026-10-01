"""Genera los iconos del botón de KiCad en icons/. Necesita Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ICONS = Path(__file__).resolve().parents[1] / "icons"
ACCENT = (0, 132, 255, 255)
THEMES = {"light": (51, 51, 51, 255), "dark": (220, 220, 220, 255)}
SIZES = (24, 48)


def draw(size: int, ink: tuple[int, int, int, int]) -> Image.Image:
    scale = 8
    big = size * scale
    u = big / 24
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    stroke = round(1.6 * u)
    pen.rounded_rectangle((6 * u, 6 * u, 18 * u, 18 * u), radius=2 * u, outline=ink, width=stroke)
    for offset in (9, 12, 15):
        pen.line((offset * u, 2.5 * u, offset * u, 6 * u), fill=ink, width=stroke)
        pen.line((offset * u, 18 * u, offset * u, 21.5 * u), fill=ink, width=stroke)
        pen.line((2.5 * u, offset * u, 6 * u, offset * u), fill=ink, width=stroke)
        pen.line((18 * u, offset * u, 21.5 * u, offset * u), fill=ink, width=stroke)
    cx, cy, r, w = 12 * u, 12 * u, 3.6 * u, 1.1 * u
    pen.polygon(
        [(cx, cy - r), (cx + w, cy - w), (cx + r, cy), (cx + w, cy + w),
         (cx, cy + r), (cx - w, cy + w), (cx - r, cy), (cx - w, cy - w)],
        fill=ACCENT,
    )
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    ICONS.mkdir(exist_ok=True)
    for theme, ink in THEMES.items():
        for size in SIZES:
            path = ICONS / f"kicad-ia-{theme}-{size}.png"
            draw(size, ink).save(path)
            print(path)


if __name__ == "__main__":
    main()
