"""Geometría del esquemático. KiCad conecta pines y cables solo si coinciden en la retícula."""

from __future__ import annotations

from dataclasses import dataclass

SCH_GRID_MM = 1.27


def snap_mm(value: float, grid: float = SCH_GRID_MM) -> float:
    return round(float(value) / grid) * grid


def rotate_mm(x_mm: float, y_mm: float, degrees: float) -> tuple[float, float]:
    turns = int(round(float(degrees) / 90.0)) % 4
    if turns == 1:
        return -y_mm, x_mm
    if turns == 2:
        return -x_mm, -y_mm
    if turns == 3:
        return y_mm, -x_mm
    return x_mm, y_mm


@dataclass(frozen=True)
class Segment:
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float

    def as_dict(self) -> dict[str, float]:
        return {
            "x1_mm": self.x1_mm,
            "y1_mm": self.y1_mm,
            "x2_mm": self.x2_mm,
            "y2_mm": self.y2_mm,
        }


def orthogonal_segments(x1: float, y1: float, x2: float, y2: float) -> list[Segment]:
    x1, y1 = snap_mm(x1), snap_mm(y1)
    x2, y2 = snap_mm(x2), snap_mm(y2)
    if x1 == x2 and y1 == y2:
        return []
    if x1 == x2 or y1 == y2:
        return [Segment(x1, y1, x2, y2)]
    return [Segment(x1, y1, x2, y1), Segment(x2, y1, x2, y2)]
