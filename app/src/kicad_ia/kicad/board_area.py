"""Rectángulo de placa a partir del contorno o de las huellas ya colocadas.

Si no hay Edge.Cuts, el área sale de las cajas de las huellas más un margen fijo.
No se inventa un tamaño cuando todavía no hay huellas en la placa.
"""

from __future__ import annotations

MARGIN_MM = 5.0


def area_from_boxes(boxes: list[tuple[float, float, float, float]], margin_mm: float = MARGIN_MM) -> dict | None:
    if not boxes:
        return None
    min_x = min(box[0] for box in boxes)
    min_y = min(box[1] for box in boxes)
    max_x = max(box[0] + box[2] for box in boxes)
    max_y = max(box[1] + box[3] for box in boxes)
    return {
        "x_mm": round(min_x - margin_mm, 1),
        "y_mm": round(min_y - margin_mm, 1),
        "width_mm": round(max_x - min_x + 2 * margin_mm, 1),
        "height_mm": round(max_y - min_y + 2 * margin_mm, 1),
        "margin_mm": margin_mm,
    }


def board_area_report(
    outline: tuple[float, float, float, float] | None,
    boxes: list[tuple[float, float, float, float]],
) -> dict:
    if outline is not None:
        x, y, width, height = (round(value, 1) for value in outline)
        return {
            "status": "defined",
            "x_mm": x,
            "y_mm": y,
            "width_mm": width,
            "height_mm": height,
            "must_tell_user": f"La placa ya tiene contorno en Edge.Cuts: {width} × {height} mm, origen ({x}, {y}) mm.",
        }
    proposal = area_from_boxes(boxes)
    if proposal is None:
        return {
            "status": "missing",
            "proposal": None,
            "must_tell_user": (
                "La placa no tiene contorno en Edge.Cuts y todavía no hay huellas para medirlo. "
                "Di al usuario que actualice con F8 y que no elija el tamaño a ojo. "
                "Cuando las huellas estén en la placa, vuelve a llamar a sync_board: ahí salen ancho y alto en mm."
            ),
        }
    return {
        "status": "missing",
        "proposal": proposal,
        "must_tell_user": (
            f"No hay contorno en Edge.Cuts. Antes de colocar o autorutear, el usuario tiene que dibujar "
            f"un rectángulo de {proposal['width_mm']} × {proposal['height_mm']} mm "
            f"con origen ({proposal['x_mm']}, {proposal['y_mm']}) mm en la capa Edge.Cuts "
            f"(cubre las huellas más {proposal['margin_mm']:.0f} mm). "
            "Repite esas medidas. No lo dejes sin área."
        ),
    }
