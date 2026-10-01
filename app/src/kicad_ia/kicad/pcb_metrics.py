"""Métricas y instantánea de una placa para comparar antes/después."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class BoardSnapshot:
    footprints: int = 0
    tracks: int = 0
    vias: int = 0
    zones: int = 0
    track_length_mm: float = 0.0
    locked_footprints: int = 0
    references: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def compare_snapshots(before: BoardSnapshot | dict, after: BoardSnapshot | dict) -> dict:
    a = before if isinstance(before, dict) else before.as_dict()
    b = after if isinstance(after, dict) else after.as_dict()
    return {
        "tracks_delta": b.get("tracks", 0) - a.get("tracks", 0),
        "vias_delta": b.get("vias", 0) - a.get("vias", 0),
        "track_length_delta_mm": round(float(b.get("track_length_mm", 0) - a.get("track_length_mm", 0)), 2),
        "footprints_delta": b.get("footprints", 0) - a.get("footprints", 0),
    }


def score_routing(drc: dict, snapshot: BoardSnapshot | dict, unconnected: int | None = None) -> dict:
    """Puntuación simple: menos errores DRC y más cobre conectado es mejor."""
    snap = snapshot if isinstance(snapshot, dict) else snapshot.as_dict()
    errors = int((drc or {}).get("error_count") or 0)
    warnings = int((drc or {}).get("warning_count") or 0)
    open_nets = int(unconnected if unconnected is not None else (drc or {}).get("unconnected", 0) or 0)
    score = 1000 - errors * 50 - warnings * 5 - open_nets * 30 + min(200, int(snap.get("tracks", 0)))
    return {
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "unconnected": open_nets,
        "tracks": snap.get("tracks", 0),
        "vias": snap.get("vias", 0),
    }


def better_than(candidate: dict, baseline: dict) -> bool:
    if candidate.get("errors", 0) > baseline.get("errors", 0):
        return False
    if candidate.get("unconnected", 0) > baseline.get("unconnected", 0):
        return False
    return candidate.get("score", 0) >= baseline.get("score", 0)
