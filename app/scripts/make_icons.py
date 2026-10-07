"""Genera los iconos del botón de KiCad en icons/. Necesita Pillow.

KiCad los abre con wxWidgets y libpng. libpng 1.6 escribe en el registro
«iCCP: known incorrect sRGB profile» y «iCCP: cHRM chunk does not match sRGB»
cuando el PNG trae el perfil sRGB antiguo de HP/Photoshop o un cHRM que no
coincide con sRGB. La guía de iconos pasa los bitmap por ``pngcrush -rem alla``,
que deja solo IHDR, IDAT e IEND: píxeles sRGB sin perfil incrustado.

Los colores son los de Icon Design Guidelines: gris primario para el trazo y
azul primario para el acento, distintos en tema claro y oscuro.
"""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ICONS = Path(__file__).resolve().parents[1] / "icons"
# https://dev-docs.kicad.org/en/rules-guidelines/icon-design/
THEMES = {
    "light": {"ink": (0x54, 0x54, 0x54, 255), "accent": (0x1A, 0x81, 0xC4, 255)},
    "dark": {"ink": (0xDE, 0xD3, 0xDD, 255), "accent": (0x42, 0xB8, 0xEB, 255)},
}
SIZES = (24, 48)
KEEP_CHUNKS = {b"IHDR", b"IDAT", b"IEND"}


def draw(size: int, ink: tuple[int, int, int, int], accent: tuple[int, int, int, int]) -> Image.Image:
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
        fill=accent,
    )
    return image.resize((size, size), Image.LANCZOS)


def save_png(image: Image.Image, path: Path) -> None:
    """Escribe un PNG sin iCCP, cHRM, sRGB, gAMA ni otros chunks auxiliares."""
    buf = BytesIO()
    image.save(buf, format="PNG")
    raw = buf.getvalue()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Pillow no escribió un PNG: {path.name}")
    out = bytearray(raw[:8])
    i = 8
    seen_ihdr = False
    while i + 8 <= len(raw):
        length = struct.unpack(">I", raw[i : i + 4])[0]
        kind = raw[i + 4 : i + 8]
        chunk = raw[i : i + 12 + length]
        if len(chunk) != 12 + length:
            raise RuntimeError(f"PNG truncado: {path.name}")
        if kind in KEEP_CHUNKS:
            out += chunk
        if kind == b"IHDR":
            seen_ihdr = True
        i += 12 + length
        if kind == b"IEND":
            break
    if not seen_ihdr or out[-8:-4] != b"IEND":
        raise RuntimeError(f"PNG incompleto: {path.name}")
    path.write_bytes(out)
    _assert_no_color_profile(path)


def _assert_no_color_profile(path: Path) -> None:
    data = path.read_bytes()
    i = 8
    kinds: list[bytes] = []
    while i + 8 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        kind = data[i + 4 : i + 8]
        kinds.append(kind)
        i += 12 + length
        if kind == b"IEND":
            break
    extra = [kind.decode("ascii") for kind in kinds if kind not in KEEP_CHUNKS]
    if extra:
        raise RuntimeError(f"{path.name} conserva chunks de color o texto: {', '.join(extra)}")


def main() -> None:
    ICONS.mkdir(exist_ok=True)
    for theme, colors in THEMES.items():
        for size in SIZES:
            path = ICONS / f"kicad-ia-{theme}-{size}.png"
            save_png(draw(size, colors["ink"], colors["accent"]), path)
            print(path)


if __name__ == "__main__":
    main()
