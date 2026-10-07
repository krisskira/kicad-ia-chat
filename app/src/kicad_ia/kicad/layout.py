"""Agrupación por función y reparto de bloques. Sirve al esquemático y a la placa."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

ANCHOR_PREFIXES = ("IC", "U", "J", "P", "BT", "SW", "Y", "X", "K", "M", "DS", "LS", "MK", "A")
_CONNECTOR_PREFIXES = ("J", "P", "BT", "CN", "CON")
_POWER_NAME = re.compile(r"^(A|D|P)?(GND|VSS|VCC|VDD|VEE|VBAT|VIN|VBUS|VSYS|VREF)\w*$|^[+-]|^\d+V\d*$|V\d", re.I)
_GROUND = re.compile(r"^(A|D|P)?(GND|VSS)\w*$", re.I)
_PREFIX = re.compile(r"^#?([A-Za-z]+)")
_MCU = re.compile(r"ESP32|STM32|RP2040|ATMEGA|NRF52|SAMD|PIC18|CH32", re.I)
_REG = re.compile(r"LDO|REGULATOR|AP2112|AMS1117|MIC52|TLV7|NCP11|LP29|TPS7|MP23", re.I)
_CONN = re.compile(r"USB|CONNECTOR|HEADER|JACK|BATTERY", re.I)


def prefix(reference: str) -> str:
    found = _PREFIX.match(reference)
    return found.group(1).upper() if found else ""


def is_anchor(reference: str) -> bool:
    return prefix(reference) in ANCHOR_PREFIXES


def is_power_net(net: dict) -> bool:
    if _POWER_NAME.search(str(net.get("name") or "")):
        return True
    return any(node.get("pintype") in ("power_in", "power_out") for node in net.get("nodes") or [])


@dataclass
class StagePlan:
    """Plan de etapas funcionales con confianza y elegibilidad de marcos."""

    groups: list[dict]
    ambiguous: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    draw_frames: bool = False
    eligible: bool = False
    auto: bool = True

    def as_dict(self) -> dict:
        return {
            "groups": self.groups,
            "ambiguous": self.ambiguous,
            "reasons": self.reasons,
            "draw_frames": self.draw_frames,
            "eligible": self.eligible,
            "auto_groups": self.auto,
        }


def auto_groups(components: list[dict], nets: list[dict]) -> list[dict]:
    """Agrupa cada pasivo con el integrado o conector al que sirve.

    Compatible con el contrato anterior: solo la lista de grupos.
    """
    return plan_stages(components, nets).groups


def plan_stages(components: list[dict], nets: list[dict], groups: list[dict] | None = None) -> StagePlan:
    """Calcula etapas, ambigüedades y si conviene dibujar recuadros."""
    order = [str(item["reference"]) for item in components]
    values = {str(item["reference"]): str(item.get("value") or "") for item in components}
    if groups:
        clean, unknown = normalize_groups(groups, order)
        reasons = []
        if unknown:
            reasons.append("Referencias desconocidas ignoradas: " + ", ".join(unknown))
        eligible, draw, frame_reasons = _frame_eligibility(clean, ambiguous=[])
        return StagePlan(
            groups=clean,
            ambiguous=[],
            reasons=reasons + frame_reasons,
            draw_frames=draw,
            eligible=eligible,
            auto=False,
        )

    anchors = [ref for ref in order if is_anchor(ref)]
    if not anchors:
        groups_out = [{"name": "Circuito", "references": order}] if order else []
        eligible, draw, frame_reasons = _frame_eligibility(groups_out, ambiguous=[])
        return StagePlan(groups=groups_out, reasons=frame_reasons, draw_frames=draw, eligible=eligible, auto=True)

    signal: dict[str, set[str]] = {ref: set() for ref in order}
    power: dict[str, set[str]] = {ref: set() for ref in order}
    drivers: dict[str, list[str]] = {}
    members: dict[str, set[str]] = {}
    for net in nets:
        name = str(net.get("name") or "")
        refs = {str(node.get("ref")) for node in net.get("nodes") or [] if node.get("ref") in signal}
        members[name] = refs
        bucket = power if is_power_net(net) else signal
        for ref in refs:
            bucket[ref].add(name)
        drivers[name] = [str(node.get("ref")) for node in net.get("nodes") or [] if node.get("pintype") == "power_out"]

    group_of: dict[str, str] = {ref: ref for ref in anchors}
    ambiguous: list[str] = []
    pending = [ref for ref in order if ref not in group_of]
    for ref in pending:
        best, tied = _best_anchor_scored(ref, anchors, signal, members)
        if tied:
            ambiguous.append(ref)
            continue
        if best:
            group_of[ref] = best

    changed = True
    while changed:
        changed = False
        for ref in pending:
            if ref in group_of or ref in ambiguous:
                continue
            neighbours = [other for net in signal[ref] for other in members[net] if other != ref and other in group_of]
            owners = {group_of[n] for n in neighbours}
            if len(owners) == 1:
                group_of[ref] = next(iter(owners))
                changed = True
            elif len(owners) > 1:
                ambiguous.append(ref)

    for ref in pending:
        if ref in group_of or ref in ambiguous:
            continue
        # Solo alimentación: preferir consumidor (power_in) sobre el regulador
        # cuando el pasivo comparte la salida con un ancla que la toma.
        nets_here = [net for net in power[ref] if not _GROUND.match(net)]
        consumers = []
        for net in nets_here:
            for other in members.get(net, set()):
                if other in anchors and other != ref:
                    consumers.append(other)
        consumers = list(dict.fromkeys(consumers))
        owner = None
        if len(consumers) == 1:
            owner = consumers[0]
        else:
            drivers_here = [driver for net in nets_here for driver in drivers.get(net, []) if driver in anchors]
            drivers_here = list(dict.fromkeys(drivers_here))
            if len(drivers_here) == 1:
                owner = drivers_here[0]
            elif len(drivers_here) > 1 or len(consumers) > 1:
                ambiguous.append(ref)
                continue
            else:
                shared = [(sum(1 for net in nets_here if anchor in members[net]), anchor) for anchor in anchors]
                shared = [pair for pair in shared if pair[0] > 0]
                if len(shared) == 1:
                    owner = shared[0][1]
                elif len(shared) > 1:
                    ambiguous.append(ref)
                    continue
        if owner:
            group_of[ref] = owner

    # Conectores: si hay ≥2 y el usuario no pasó groups, fusionar en «Conectores»
    # solo cuando no tienen pasivos de señal propios (solo ancla suelta).
    connector_anchors = [a for a in anchors if prefix(a) in _CONNECTOR_PREFIXES]
    merge_connectors = False
    if len(connector_anchors) >= 2:
        lonely = []
        for anchor in connector_anchors:
            members_of = [ref for ref in order if group_of.get(ref) == anchor]
            if members_of == [anchor]:
                lonely.append(anchor)
        if len(lonely) >= 2:
            merge_connectors = True
            for anchor in lonely:
                group_of[anchor] = "__connectors__"

    groups_out: list[dict] = []
    if merge_connectors:
        refs = [ref for ref in order if group_of.get(ref) == "__connectors__"]
        if refs:
            groups_out.append({"name": "Conectores", "references": refs})
    for anchor in anchors:
        if merge_connectors and anchor in connector_anchors and group_of.get(anchor) == "__connectors__":
            continue
        refs = [ref for ref in order if group_of.get(ref) == anchor]
        if not refs:
            continue
        groups_out.append({"name": _stage_name(anchor, values.get(anchor, ""), values), "references": refs})

    loose = [ref for ref in order if ref not in group_of and ref not in ambiguous]
    loose.extend(ref for ref in ambiguous if ref not in loose)
    # Ambiguos van a Otros; se listan aparte para que el modelo pregunte.
    if loose:
        groups_out.append({"name": "Otros", "references": [ref for ref in order if ref in set(loose)]})

    reasons = []
    if ambiguous:
        reasons.append(
            "Referencias ambiguas (comparten señal o alimentación con varios anclas): " + ", ".join(sorted(set(ambiguous)))
        )
    eligible, draw, frame_reasons = _frame_eligibility(groups_out, ambiguous=list(set(ambiguous)))
    return StagePlan(
        groups=groups_out,
        ambiguous=sorted(set(ambiguous)),
        reasons=reasons + frame_reasons,
        draw_frames=draw,
        eligible=eligible,
        auto=True,
    )


def _best_anchor_scored(
    ref: str, anchors: list[str], signal: dict[str, set[str]], members: dict[str, set[str]]
) -> tuple[str | None, bool]:
    scores = []
    for anchor in anchors:
        count = sum(1 for net in signal[ref] if anchor in members[net])
        if count:
            scores.append((count, -anchors.index(anchor), anchor))
    if not scores:
        return None, False
    scores.sort(reverse=True)
    best = scores[0]
    # Empate de puntuación → ambigüedad (no decidir).
    if len(scores) > 1 and scores[1][0] == best[0]:
        return None, True
    return best[2], False


def _best_anchor(ref: str, anchors: list[str], signal: dict[str, set[str]], members: dict[str, set[str]]) -> str | None:
    best, tied = _best_anchor_scored(ref, anchors, signal, members)
    return None if tied else best


def _stage_name(anchor: str, value: str, values: dict[str, str]) -> str:
    blob = f"{anchor} {value}"
    if _REG.search(blob):
        return f"Alimentación ({anchor})"
    if _MCU.search(blob):
        return f"Microcontrolador ({anchor})"
    if _CONN.search(blob) or prefix(anchor) in _CONNECTOR_PREFIXES:
        return f"Conector ({anchor})"
    label = f"{anchor} {value}".strip()
    return label or anchor


def _frame_eligibility(groups: list[dict], ambiguous: list[str]) -> tuple[bool, bool, list[str]]:
    """eligible, draw_frames, reasons."""
    useful = [g for g in groups if g.get("references")]
    named = [g for g in useful if g.get("name") != "Otros"]
    reasons: list[str] = []
    if ambiguous:
        reasons.append("Hay ambigüedades: mejor pasar groups explícitos o confirmar antes de enmarcar.")
        return False, False, reasons
    if len(named) < 2:
        reasons.append("Solo hay una etapa útil: se reordena sin recuadros.")
        return False, False, reasons
    # «Otros» con una sola pieza no justifica un marco propio; se dibuja el resto.
    draw = True
    reasons.append(f"Elegible: {len(named)} etapas con nombres propios.")
    return True, draw, reasons


def normalize_groups(groups: list[dict], references: list[str]) -> tuple[list[dict], list[str]]:
    """Quita referencias que no existen, evita repetidas y deja las sueltas en «Otros»."""
    known = set(references)
    seen: set[str] = set()
    clean = []
    unknown = []
    for group in groups:
        refs = []
        for ref in group.get("references") or []:
            ref = str(ref)
            if ref not in known:
                unknown.append(ref)
            elif ref not in seen:
                refs.append(ref)
                seen.add(ref)
        if refs:
            clean.append({"name": str(group.get("name") or "Grupo").strip() or "Grupo", "references": refs})
    loose = [ref for ref in references if ref not in seen]
    if loose:
        clean.append({"name": "Otros", "references": loose})
    return clean, unknown


@dataclass
class Box:
    key: str
    width: float
    height: float
    x: float = 0.0
    y: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2, self.y + self.height / 2


def shelf_pack(boxes: list[Box], max_width: float, gap: float) -> tuple[float, float]:
    """Coloca de izquierda a derecha y salta de fila. Devuelve ancho y alto ocupados."""
    x = y = row_height = used_width = 0.0
    for box in boxes:
        if x > 0 and x + box.width > max_width:
            x = 0.0
            y += row_height + gap
            row_height = 0.0
        box.x, box.y = x, y
        x += box.width + gap
        row_height = max(row_height, box.height)
        used_width = max(used_width, box.x + box.width)
    return used_width, y + row_height


def group_layout(
    sizes: dict[str, tuple[float, float]],
    groups: list[dict],
    max_width: float | None,
    item_gap: float,
    group_gap: float,
    padding: float,
    header: float = 0.0,
) -> tuple[dict[str, tuple[float, float]], list[Box], tuple[float, float]]:
    """Centros de cada referencia y caja de cada grupo, en coordenadas relativas al origen.

    Con max_width None el ancho se elige para que el conjunto quede casi cuadrado.
    """
    blocks: list[tuple[Box, list[Box]]] = []
    for group in groups:
        items = [Box(ref, *sizes[ref]) for ref in group["references"] if ref in sizes]
        if not items:
            continue
        items.sort(key=lambda box: box.width * box.height, reverse=True)
        area = sum((box.width + item_gap) * (box.height + item_gap) for box in items)
        inner = max(max(box.width for box in items), math.sqrt(area) * 1.4)
        if max_width:
            inner = min(inner, max_width - 2 * padding)
        width, height = shelf_pack(items, inner, item_gap)
        blocks.append((Box(group["name"], width + 2 * padding, height + 2 * padding + header), items))

    if not max_width:
        area = sum((block.width + group_gap) * (block.height + group_gap) for block, _ in blocks)
        max_width = max([block.width for block, _ in blocks] + [math.sqrt(area) * 1.15])
    shelf_pack([block for block, _ in blocks], max_width, group_gap)
    centers: dict[str, tuple[float, float]] = {}
    for block, items in blocks:
        for item in items:
            cx, cy = item.center
            centers[item.key] = (block.x + padding + cx, block.y + padding + header + cy)
    width = max((block.x + block.width for block, _ in blocks), default=0.0)
    height = max((block.y + block.height for block, _ in blocks), default=0.0)
    return centers, [block for block, _ in blocks], (width, height)
