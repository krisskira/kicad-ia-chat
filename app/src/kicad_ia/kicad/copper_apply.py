"""Aplicar cobre de una placa candidata (tras FreeRouting) a la placa viva por kipy."""

from __future__ import annotations

from pathlib import Path

from kicad_ia.kicad.sexpr import child, children, number, parse


LAYER_MAP = {
    "F.Cu": "BL_F_Cu",
    "B.Cu": "BL_B_Cu",
    "In1.Cu": "BL_In1_Cu",
    "In2.Cu": "BL_In2_Cu",
}


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
        net = child(seg, "net")
        if not start or not end or not width or not layer or not net:
            continue
        segments.append(
            {
                "start": (number(start[1]), number(start[2])),
                "end": (number(end[1]), number(end[2])),
                "width_mm": number(width[1]),
                "layer": str(layer[1]),
                "net": int(number(net[1])),
                "net_name": net_names.get(int(number(net[1])), ""),
            }
        )
    vias = []
    for via in children(root, "via"):
        at = child(via, "at")
        size = child(via, "size")
        drill = child(via, "drill")
        net = child(via, "net")
        if not at or not size or not net:
            continue
        vias.append(
            {
                "x_mm": number(at[1]),
                "y_mm": number(at[2]),
                "size_mm": number(size[1]),
                "drill_mm": number(drill[1]) if drill else number(size[1]) / 2,
                "net": int(number(net[1])),
                "net_name": net_names.get(int(number(net[1])), ""),
            }
        )
    return {"nets": net_names, "segments": segments, "vias": vias}


def apply_copper_to_board(board, candidate: Path) -> dict:
    """Borra pistas/vías actuales y crea las del candidato. board es kipy Board."""
    from kipy.board_types import Track, Via
    from kipy.geometry import Vector2
    from kipy.proto.board.board_types_pb2 import BoardLayer

    copper = parse_copper(candidate)
    nets_by_name = {}
    for net in list(board.get_nets() or []):
        name = str(getattr(net, "name", "") or "")
        if name:
            nets_by_name[name.lstrip("/")] = net

    existing = list(board.get_tracks() or []) + list(board.get_vias() or [])
    if existing:
        board.remove_items(existing)

    created_tracks = []
    missing_nets = set()
    for seg in copper["segments"]:
        net = nets_by_name.get(seg["net_name"].lstrip("/"))
        if net is None:
            missing_nets.add(seg["net_name"] or str(seg["net"]))
            continue
        layer_name = LAYER_MAP.get(seg["layer"])
        if not layer_name:
            continue
        track = Track()
        track.start = Vector2.from_xy_mm(*seg["start"]) if hasattr(Vector2, "from_xy_mm") else Vector2.from_xy(
            int(seg["start"][0] * 1_000_000), int(seg["start"][1] * 1_000_000)
        )
        track.end = Vector2.from_xy_mm(*seg["end"]) if hasattr(Vector2, "from_xy_mm") else Vector2.from_xy(
            int(seg["end"][0] * 1_000_000), int(seg["end"][1] * 1_000_000)
        )
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
        via.position = Vector2.from_xy_mm(via_spec["x_mm"], via_spec["y_mm"]) if hasattr(Vector2, "from_xy_mm") else Vector2.from_xy(
            int(via_spec["x_mm"] * 1_000_000), int(via_spec["y_mm"] * 1_000_000)
        )
        via.diameter = int(round(via_spec["size_mm"] * 1_000_000))
        via.drill_diameter = int(round(via_spec["drill_mm"] * 1_000_000))
        via.net = net
        created_vias.append(via)

    if created_tracks:
        board.create_items(created_tracks)
    if created_vias:
        board.create_items(created_vias)
    return {
        "ok": not missing_nets,
        "tracks_created": len(created_tracks),
        "vias_created": len(created_vias),
        "removed": len(existing),
        "missing_nets": sorted(missing_nets)[:20],
    }
