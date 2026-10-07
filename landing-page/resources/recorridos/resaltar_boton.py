"""Resalta el icono de KiCad IA en la captura real del editor de placas.

La captura es la ventana de KiCad, no la ilustración de escenario.html. El
resalte copia el del tutorial: marco ámbar, halo blanco y cursor.

Desde la raíz del repo:

  python3 landing-page/resources/recorridos/resaltar_boton.py

Escribe el fotograma 01-boton.webp en los dos idiomas del recorrido.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "fuentes" / "boton-kicad.png"
OUT = HERE.parents[1] / "public" / "media" / "recorridos" / "de-la-orden-a-la-pcb"
MARK = (245, 165, 36)
# Icono del plugin en la barra superior de la captura de 2032×1162.
ICON = (1294, 72, 1313, 95)
PAD = 8
W, H = 1920, 1080


def cursor(draw: ImageDraw.ImageDraw, tip: tuple[int, int], size: int = 38) -> None:
    """Punta en `tip`. Misma forma que el cursor de escenario.html."""
    ox, oy = tip
    scale = size / 24
    points = [(4, 2), (20, 12.5), (12.8, 13.9), (17.1, 21.5), (14.1, 23.1), (9.8, 15.4), (4, 20)]
    shape = [(ox + (x - 4) * scale, oy + (y - 2) * scale) for x, y in points]
    draw.polygon(shape, fill=(255, 255, 255, 255), outline=(17, 17, 17, 255))


def highlighted(source: Path) -> Image.Image:
    base = Image.open(source).convert("RGBA")
    x0, y0, x1, y1 = (ICON[0] - PAD, ICON[1] - PAD, ICON[2] + PAD, ICON[3] + PAD)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for spread, alpha, width in ((16, 50, 8), (8, 90, 6)):
        draw.rounded_rectangle(
            [x0 - spread, y0 - spread, x1 + spread, y1 + spread],
            radius=12 + spread // 2,
            outline=(*MARK, alpha),
            width=width,
        )
    draw.rounded_rectangle([x0 - 3, y0 - 3, x1 + 3, y1 + 3], radius=14, outline=(255, 255, 255, 190), width=3)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=12, outline=(*MARK, 255), width=4)
    cursor(draw, (ICON[2] - 2, ICON[3] - 6))
    framed = Image.alpha_composite(base, layer).convert("RGB")
    scale = min(W / framed.width, H / framed.height)
    resized = framed.resize((round(framed.width * scale), round(framed.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(resized, ((W - resized.width) // 2, (H - resized.height) // 2))
    return canvas


def main() -> None:
    image = highlighted(SOURCE)
    for lang in ("es", "en"):
        folder = OUT / lang
        folder.mkdir(parents=True, exist_ok=True)
        webp = folder / "01-boton.webp"
        image.save(webp, "WEBP", quality=82)
        print(webp)


if __name__ == "__main__":
    main()
