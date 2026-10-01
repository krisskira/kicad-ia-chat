"""Símbolos colocados y cables que salen de conectar un pin con otro."""

from __future__ import annotations

from dataclasses import dataclass, field

from kicad_ia.kicad.catalog import CatalogPin
from kicad_ia.kicad.geometry import SCH_GRID_MM, rotate_mm, snap_mm


@dataclass
class PlacedSymbol:
    lib_id: str
    reference: str
    value: str
    footprint: str
    x_mm: float
    y_mm: float
    orientation: float
    pins: list[CatalogPin] = field(default_factory=list)

    def pin_position(self, number: str) -> tuple[float, float] | None:
        for pin in self.pins:
            if pin.number == str(number):
                rotated_x, rotated_y = rotate_mm(pin.x_mm, pin.y_mm, self.orientation)
                return snap_mm(self.x_mm + rotated_x), snap_mm(self.y_mm + rotated_y)
        return None

    def as_dict(self) -> dict:
        return {
            "lib_id": self.lib_id,
            "reference": self.reference,
            "value": self.value,
            "footprint": self.footprint,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "orientation": self.orientation,
            "pins": [pin.as_dict() for pin in self.pins],
        }


@dataclass
class PlacedFootprint:
    reference: str
    footprint: str
    value: str
    x_mm: float
    y_mm: float
    model: str

    def as_dict(self) -> dict:
        return {
            "reference": self.reference,
            "footprint": self.footprint,
            "value": self.value,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "model": self.model,
        }


def snapped_symbol(spec: dict, pins: list[CatalogPin]) -> PlacedSymbol:
    return PlacedSymbol(
        lib_id=str(spec["lib_id"]),
        reference=str(spec.get("reference") or ""),
        value=str(spec.get("value") or ""),
        footprint=str(spec.get("footprint") or ""),
        x_mm=snap_mm(spec["x_mm"]),
        y_mm=snap_mm(spec["y_mm"]),
        orientation=float(spec.get("orientation") or 0),
        pins=list(pins),
    )


def grid_note() -> str:
    return f"Retícula del esquemático: {SCH_GRID_MM} mm."
