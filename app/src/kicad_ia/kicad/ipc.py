"""Perfil IPC Clase 2 para pre-chequeo de colocación y diseño de placa.

No es una certificación IPC-A-610 ni IPC-6012: son reglas de diseño
inspiradas en IPC-2221C / IPC-7351, más el DRC real de KiCad.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from kicad_ia.kicad.layout import prefix

# Holguras típicas de ensamblaje Clase 2 (mm). Documentadas como pre-chequeo.
CLASS2 = {
    "name": "IPC Class 2",
    "standard_refs": ["IPC-2221C §8", "IPC-7351 (land patterns / adjacent spacing)"],
    "disclaimer": (
        "Pre-chequeo de diseño IPC Clase 2. No sustituye una inspección ni una "
        "certificación IPC-A-610 / IPC-6012."
    ),
    "courtyard_clearance_mm": 0.25,
    "body_clearance_mm": 0.50,
    "edge_clearance_mm": 1.00,
    "connector_edge_max_mm": 5.00,
    "decoupling_max_mm": 5.00,
    "thermal_keepout_mm": 2.00,
    "silk_to_pad_mm": 0.15,
    "min_track_mm": 0.15,
    "min_clearance_mm": 0.15,
    "min_via_drill_mm": 0.20,
    "min_via_diameter_mm": 0.40,
    "preferred_grid_mm": 0.25,
}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # error | warning | info
    message: str
    references: tuple[str, ...] = ()
    auto_fixable: bool = False
    fix: str = ""

    def as_dict(self) -> dict:
        data = asdict(self)
        data["references"] = list(self.references)
        return data


_CONNECTOR = re.compile(r"^(J|P|CONN|USB|BT|MK)", re.I)
_DECOUPLE = re.compile(r"^C\d+", re.I)
_IC = re.compile(r"^(U|IC)\d+", re.I)
_PASSIVE = re.compile(r"^(R|C|L)\d+", re.I)
_POWER_NET = re.compile(r"(GND|VSS|VCC|VDD|VBAT|VIN|VBUS|\+?\d+V)", re.I)


def profile(class_id: str = "2") -> dict:
    if str(class_id) != "2":
        # Solo Clase 2 está calibrada; otras clases caen al mismo perfil con aviso.
        data = dict(CLASS2)
        data["name"] = f"IPC Class {class_id} (usando umbrales de Clase 2)"
        data["disclaimer"] = CLASS2["disclaimer"] + f" Pediste Clase {class_id}; aplico umbrales de Clase 2."
        return data
    return dict(CLASS2)


def audit_placement(
    footprints: list[dict],
    outline: tuple[float, float, float, float] | None,
    nets: list[dict] | None = None,
    class_id: str = "2",
) -> list[Finding]:
    """footprints: reference, x_mm, y_mm, width_mm, height_mm, angle?, locked?, value?."""
    rules = profile(class_id)
    findings: list[Finding] = []
    if not footprints:
        return [Finding("pcb.empty", "error", "La placa no tiene huellas.", auto_fixable=False)]

    if outline is None:
        findings.append(
            Finding(
                "pcb.no_outline",
                "warning",
                "No hay contorno en Edge.Cuts; no puedo comprobar la distancia al borde.",
            )
        )
    else:
        ox, oy, ow, oh = outline
        edge = rules["edge_clearance_mm"]
        for fp in footprints:
            half_w = float(fp.get("width_mm") or 2) / 2
            half_h = float(fp.get("height_mm") or 2) / 2
            x, y = float(fp["x_mm"]), float(fp["y_mm"])
            left, right = x - half_w, x + half_w
            top, bottom = y - half_h, y + half_h
            if left < ox or right > ox + ow or top < oy or bottom > oy + oh:
                findings.append(
                    Finding(
                        "ipc.outside_board",
                        "error",
                        f"{fp['reference']} sobresale del contorno de la placa.",
                        (fp["reference"],),
                        auto_fixable=True,
                        fix="move_inside",
                    )
                )
            elif (
                left < ox + edge
                or right > ox + ow - edge
                or top < oy + edge
                or bottom > oy + oh - edge
            ):
                if not _CONNECTOR.match(str(fp["reference"])):
                    findings.append(
                        Finding(
                            "ipc.edge_clearance",
                            "warning",
                            f"{fp['reference']} está a menos de {edge} mm del borde (IPC-2221).",
                            (fp["reference"],),
                            auto_fixable=True,
                            fix="push_from_edge",
                        )
                    )

    clearance = rules["body_clearance_mm"]
    for index, a in enumerate(footprints):
        for b in footprints[index + 1 :]:
            gap = _gap(a, b)
            if gap < 0:
                findings.append(
                    Finding(
                        "ipc.overlap",
                        "error",
                        f"{a['reference']} y {b['reference']} se solapan.",
                        (a["reference"], b["reference"]),
                        auto_fixable=True,
                        fix="separate",
                    )
                )
            elif gap < clearance:
                findings.append(
                    Finding(
                        "ipc.body_clearance",
                        "warning",
                        f"{a['reference']} y {b['reference']} están {gap:.2f} mm "
                        f"(mínimo recomendado {clearance} mm, IPC-7351).",
                        (a["reference"], b["reference"]),
                        auto_fixable=True,
                        fix="separate",
                    )
                )

    if outline:
        ox, oy, ow, oh = outline
        for fp in footprints:
            if not _CONNECTOR.match(str(fp["reference"])):
                continue
            dist = min(
                float(fp["x_mm"]) - ox,
                oy + oh - float(fp["y_mm"]),
                ox + ow - float(fp["x_mm"]),
                float(fp["y_mm"]) - oy,
            )
            if dist > rules["connector_edge_max_mm"]:
                findings.append(
                    Finding(
                        "ipc.connector_edge",
                        "info",
                        f"{fp['reference']} está lejos del borde ({dist:.1f} mm); "
                        "los conectores suelen ir al perímetro.",
                        (fp["reference"],),
                    )
                )

    if nets:
        findings.extend(_decoupling_findings(footprints, nets, rules["decoupling_max_mm"]))

    angles = [float(fp.get("angle") or 0) % 180 for fp in footprints if _PASSIVE.match(str(fp["reference"]))]
    if angles and len({round(a) for a in angles}) > 2:
        findings.append(
            Finding(
                "ipc.orientation",
                "info",
                "Hay pasivos con muchas orientaciones distintas; conviene alinearlos a 0°/90°.",
            )
        )

    return findings


def _gap(a: dict, b: dict) -> float:
    aw, ah = float(a.get("width_mm") or 2) / 2, float(a.get("height_mm") or 2) / 2
    bw, bh = float(b.get("width_mm") or 2) / 2, float(b.get("height_mm") or 2) / 2
    dx = abs(float(a["x_mm"]) - float(b["x_mm"])) - (aw + bw)
    dy = abs(float(a["y_mm"]) - float(b["y_mm"])) - (ah + bh)
    if dx < 0 and dy < 0:
        return -min(-dx, -dy)
    if dx < 0:
        return dy
    if dy < 0:
        return dx
    return math.hypot(dx, dy)


def _decoupling_findings(footprints: list[dict], nets: list[dict], limit: float) -> list[Finding]:
    by_ref = {str(fp["reference"]): fp for fp in footprints}
    findings = []
    power_caps: dict[str, list[str]] = {}
    for net in nets:
        name = str(net.get("name") or "")
        if not _POWER_NET.search(name) or re.search(r"GND|VSS", name, re.I):
            continue
        caps = [str(n.get("ref")) for n in net.get("nodes") or [] if _DECOUPLE.match(str(n.get("ref") or ""))]
        ics = [str(n.get("ref")) for n in net.get("nodes") or [] if _IC.match(str(n.get("ref") or ""))]
        for cap in caps:
            for ic in ics:
                power_caps.setdefault(cap, []).append(ic)
    for cap, ics in power_caps.items():
        if cap not in by_ref:
            continue
        distances = []
        for ic in ics:
            if ic not in by_ref:
                continue
            distances.append(
                (
                    math.hypot(float(by_ref[cap]["x_mm"]) - float(by_ref[ic]["x_mm"]), float(by_ref[cap]["y_mm"]) - float(by_ref[ic]["y_mm"])),
                    ic,
                )
            )
        if not distances:
            continue
        best, ic = min(distances)
        if best > limit:
            findings.append(
                Finding(
                    "ipc.decoupling",
                    "warning",
                    f"{cap} está a {best:.1f} mm de {ic}; los desacoplos deben ir junto al IC (≤ {limit} mm).",
                    (cap, ic),
                    auto_fixable=True,
                    fix="pull_to_ic",
                )
            )
    return findings


def place_ipc(
    footprints: list[dict],
    groups: list[dict],
    outline: tuple[float, float, float, float] | None,
    class_id: str = "2",
) -> tuple[list[dict], list[Finding]]:
    """Calcula una colocación respetando holguras IPC. No mueve locked=True."""
    from kicad_ia.kicad.layout import group_layout, normalize_groups

    rules = profile(class_id)
    locked = {str(fp["reference"]): fp for fp in footprints if fp.get("locked")}
    movable = [fp for fp in footprints if not fp.get("locked")]
    if not movable:
        return [], [Finding("ipc.all_locked", "warning", "Todas las huellas están bloqueadas.")]

    sizes = {
        str(fp["reference"]): (
            float(fp.get("width_mm") or 2) + rules["body_clearance_mm"],
            float(fp.get("height_mm") or 2) + rules["body_clearance_mm"],
        )
        for fp in movable
    }
    refs = list(sizes)
    clean, unknown = normalize_groups(groups or [{"name": "Circuito", "references": refs}], refs)
    # Conectores primero al borde: reordenar grupos
    clean = _prioritize_connectors(clean)

    margin = rules["edge_clearance_mm"]
    if outline:
        ox, oy, ow, oh = outline
        origin = (ox + margin, oy + margin)
        max_width = max(10.0, ow - 2 * margin)
    else:
        xs = [float(fp["x_mm"]) for fp in footprints]
        ys = [float(fp["y_mm"]) for fp in footprints]
        origin = (min(xs), min(ys))
        max_width = None

    centers, _blocks, (_w, _h) = group_layout(
        sizes,
        clean,
        max_width,
        item_gap=rules["body_clearance_mm"],
        group_gap=rules["thermal_keepout_mm"],
        padding=rules["courtyard_clearance_mm"],
    )

    plan = []
    for fp in movable:
        ref = str(fp["reference"])
        if ref not in centers:
            continue
        cx, cy = centers[ref]
        angle = 0.0 if _PASSIVE.match(ref) else float(fp.get("angle") or 0)
        # Offset: el layout da centros de caja; la posición de la huella es el origen del footprint.
        ox_off = float(fp.get("origin_offset_x_mm") or 0)
        oy_off = float(fp.get("origin_offset_y_mm") or 0)
        plan.append(
            {
                "reference": ref,
                "x_mm": round(origin[0] + cx + ox_off, 3),
                "y_mm": round(origin[1] + cy + oy_off, 3),
                "angle": angle,
            }
        )

    # Empujar conectores hacia el borde más cercano
    if outline:
        for item in plan:
            if not _CONNECTOR.match(item["reference"]):
                continue
            item["x_mm"], item["y_mm"] = _snap_to_edge(
                item["x_mm"], item["y_mm"], outline, margin, sizes.get(item["reference"], (4, 4))
            )

    proposed = {**{str(fp["reference"]): dict(fp) for fp in footprints}, **{p["reference"]: {**next(f for f in footprints if f["reference"] == p["reference"]), **p} for p in plan}}
    audit = audit_placement(list(proposed.values()), outline, class_id=class_id)
    if unknown:
        audit.append(Finding("ipc.unknown_refs", "info", f"Referencias desconocidas en groups: {', '.join(unknown)}."))
    if locked:
        audit.append(
            Finding(
                "ipc.locked_kept",
                "info",
                f"No moví {len(locked)} huella(s) bloqueada(s): {', '.join(sorted(locked))}.",
                tuple(sorted(locked)),
            )
        )
    return plan, audit


def _prioritize_connectors(groups: list[dict]) -> list[dict]:
    connectors, rest = [], []
    for group in groups:
        refs = group.get("references") or []
        if refs and all(_CONNECTOR.match(str(ref)) or prefix(str(ref)) in {"J", "P", "BT"} for ref in refs):
            connectors.append(group)
        else:
            # Separar conectores sueltos
            conn = [r for r in refs if _CONNECTOR.match(str(r))]
            other = [r for r in refs if r not in conn]
            if conn:
                connectors.append({"name": f"{group.get('name', 'Conectores')} · borde", "references": conn})
            if other:
                rest.append({"name": group.get("name") or "Grupo", "references": other})
    return connectors + rest


def _snap_to_edge(
    x: float,
    y: float,
    outline: tuple[float, float, float, float],
    margin: float,
    size: tuple[float, float],
) -> tuple[float, float]:
    ox, oy, ow, oh = outline
    half_w, half_h = size[0] / 2, size[1] / 2
    candidates = [
        (ox + margin + half_w, y),
        (ox + ow - margin - half_w, y),
        (x, oy + margin + half_h),
        (x, oy + oh - margin - half_h),
    ]
    return min(candidates, key=lambda p: abs(p[0] - x) + abs(p[1] - y))


def safe_fixes(findings: list[Finding], footprints: list[dict], outline: tuple[float, float, float, float] | None) -> list[dict]:
    """Genera movimientos seguros a partir de hallazgos auto_fixable."""
    by_ref = {str(fp["reference"]): dict(fp) for fp in footprints}
    moves: dict[str, dict] = {}
    rules = profile()
    for finding in findings:
        if not finding.auto_fixable or not finding.references:
            continue
        if finding.fix == "push_from_edge" and outline:
            ref = finding.references[0]
            fp = by_ref.get(ref)
            if not fp:
                continue
            ox, oy, ow, oh = outline
            edge = rules["edge_clearance_mm"]
            half_w = float(fp.get("width_mm") or 2) / 2
            half_h = float(fp.get("height_mm") or 2) / 2
            x = min(max(float(fp["x_mm"]), ox + edge + half_w), ox + ow - edge - half_w)
            y = min(max(float(fp["y_mm"]), oy + edge + half_h), oy + oh - edge - half_h)
            moves[ref] = {"reference": ref, "x_mm": round(x, 3), "y_mm": round(y, 3)}
        elif finding.fix == "move_inside" and outline:
            ref = finding.references[0]
            fp = by_ref.get(ref)
            if not fp:
                continue
            ox, oy, ow, oh = outline
            edge = rules["edge_clearance_mm"]
            half_w = float(fp.get("width_mm") or 2) / 2
            half_h = float(fp.get("height_mm") or 2) / 2
            x = min(max(float(fp["x_mm"]), ox + edge + half_w), ox + ow - edge - half_w)
            y = min(max(float(fp["y_mm"]), oy + edge + half_h), oy + oh - edge - half_h)
            moves[ref] = {"reference": ref, "x_mm": round(x, 3), "y_mm": round(y, 3)}
        elif finding.fix == "separate" and len(finding.references) >= 2:
            a, b = finding.references[0], finding.references[1]
            fa, fb = by_ref.get(a), by_ref.get(b)
            if not fa or not fb:
                continue
            dx = float(fb["x_mm"]) - float(fa["x_mm"])
            dy = float(fb["y_mm"]) - float(fa["y_mm"])
            dist = math.hypot(dx, dy) or 0.1
            need = rules["body_clearance_mm"] + 0.5
            scale = (need / dist) if dist < need else 1.0
            if scale > 1:
                moves[b] = {
                    "reference": b,
                    "x_mm": round(float(fa["x_mm"]) + dx * scale, 3),
                    "y_mm": round(float(fa["y_mm"]) + dy * scale, 3),
                }
        elif finding.fix == "pull_to_ic" and len(finding.references) >= 2:
            cap, ic = finding.references[0], finding.references[1]
            fc, fi = by_ref.get(cap), by_ref.get(ic)
            if not fc or not fi:
                continue
            dx = float(fc["x_mm"]) - float(fi["x_mm"])
            dy = float(fc["y_mm"]) - float(fi["y_mm"])
            dist = math.hypot(dx, dy) or 1.0
            target = min(dist, rules["decoupling_max_mm"] * 0.6)
            moves[cap] = {
                "reference": cap,
                "x_mm": round(float(fi["x_mm"]) + dx / dist * target, 3),
                "y_mm": round(float(fi["y_mm"]) + dy / dist * target, 3),
            }
    return list(moves.values())
