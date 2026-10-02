"""Aplicar cobre de una placa candidata (tras FreeRouting) a la placa viva por kipy."""

from __future__ import annotations

from pathlib import Path

from kicad_ia.kicad.sexpr import Sym, child, children, number, parse


LAYER_MAP = {
    "F.Cu": "BL_F_Cu",
    "B.Cu": "BL_B_Cu",
    "In1.Cu": "BL_In1_Cu",
    "In2.Cu": "BL_In2_Cu",
}


def _net_ref(net: list | None, net_names: dict[int, str]) -> tuple[int, str] | None:
    """KiCad 9 escribe `(net 3)` y busca el nombre arriba; KiCad 10 escribe `(net "/GND")`."""
    if not net or len(net) < 2:
        return None
    value = net[1]
    if isinstance(value, Sym):
        code = int(number(value, -1))
        if code < 0:
            return None
        return code, net_names.get(code, "")
    return -1, str(value)


def parse_copper(board_file: Path) -> dict:
    """Lee segmentos y vías del .kicad_pcb y el mapa número→nombre de red."""
    root = parse(board_file.read_text(encoding="utf-8"))[0]
    net_names: dict[int, str] = {}
    for net in children(root, "net"):
        if len(net) >= 3:
            try:
                net_names[int(number(net[1]))] = str(net[2])
            except Exception:
                continue
    segments = []
    for seg in children(root, "segment"):
        start = child(seg, "start")
        end = child(seg, "end")
        width = child(seg, "width")
        layer = child(seg, "layer")
        ref = _net_ref(child(seg, "net"), net_names)
        if not start or not end or not width or not layer or ref is None:
            continue
        segments.append(
            {
                "start": (number(start[1]), number(start[2])),
                "end": (number(end[1]), number(end[2])),
                "width_mm": number(width[1]),
                "layer": str(layer[1]),
                "net": ref[0],
                "net_name": ref[1],
            }
        )
    vias = []
    for via in children(root, "via"):
        at = child(via, "at")
        size = child(via, "size")
        drill = child(via, "drill")
        ref = _net_ref(child(via, "net"), net_names)
        if not at or not size or ref is None:
            continue
        vias.append(
            {
                "x_mm": number(at[1]),
                "y_mm": number(at[2]),
                "size_mm": number(size[1]),
                "drill_mm": number(drill[1]) if drill else number(size[1]) / 2,
                "net": ref[0],
                "net_name": ref[1],
            }
        )
    return {"nets": net_names, "segments": segments, "vias": vias}


def _vector(x_mm: float, y_mm: float):
    from kipy.geometry import Vector2

    if hasattr(Vector2, "from_xy_mm"):
        return Vector2.from_xy_mm(x_mm, y_mm)
    return Vector2.from_xy(int(round(x_mm * 1_000_000)), int(round(y_mm * 1_000_000)))


def apply_copper_to_board(board, candidate: Path) -> dict:
    """Sustituye pistas/vías de la placa por las del candidato. board es kipy Board.

    Si alguna red del candidato no existe en la placa viva, no toca nada.
    """
    from kipy.board_types import Track, Via
    from kipy.proto.board.board_types_pb2 import BoardLayer

    copper = parse_copper(candidate)
    nets_by_name = {}
    for net in list(board.get_nets() or []):
        name = str(getattr(net, "name", "") or "")
        if name:
            nets_by_name[name.lstrip("/")] = net

    created_tracks = []
    missing_nets = set()
    skipped_layers = set()
    for seg in copper["segments"]:
        net = nets_by_name.get(seg["net_name"].lstrip("/"))
        if net is None:
            missing_nets.add(seg["net_name"] or str(seg["net"]))
            continue
        layer_name = LAYER_MAP.get(seg["layer"])
        if not layer_name:
            skipped_layers.add(seg["layer"])
            continue
        track = Track()
        track.start = _vector(*seg["start"])
        track.end = _vector(*seg["end"])
        track.width = int(round(seg["width_mm"] * 1_000_000))
        track.layer = getattr(BoardLayer, layer_name)
        track.net = net
        created_tracks.append(track)

    created_vias = []
    for via_spec in copper["vias"]:
        net = nets_by_name.get(via_spec["net_name"].lstrip("/"))
        if net is None:
            missing_nets.add(via_spec["net_name"] or str(via_spec["net"]))
            continue
        via = Via()
        via.position = _vector(via_spec["x_mm"], via_spec["y_mm"])
        via.diameter = int(round(via_spec["size_mm"] * 1_000_000))
        via.drill_diameter = int(round(via_spec["drill_mm"] * 1_000_000))
        via.net = net
        created_vias.append(via)

    if missing_nets or skipped_layers or not (created_tracks or created_vias):
        return {
            "ok": False,
            "tracks_created": 0,
            "vias_created": 0,
            "removed": 0,
            "missing_nets": sorted(missing_nets)[:20],
            "skipped_layers": sorted(skipped_layers),
            "error": "No apliqué nada: el candidato no coincide con la placa viva.",
        }

    existing = list(board.get_tracks() or []) + list(board.get_vias() or [])
    if existing:
        board.remove_items(existing)
    if created_tracks:
        board.create_items(created_tracks)
    if created_vias:
        board.create_items(created_vias)
    return {
        "ok": True,
        "tracks_created": len(created_tracks),
        "vias_created": len(created_vias),
        "removed": len(existing),
        "missing_nets": [],
    }
