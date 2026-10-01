"""Agrupación por función y reparto de bloques. Sirve al esquemático y a la placa."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

ANCHOR_PREFIXES = ("IC", "U", "J", "P", "BT", "SW", "Y", "X", "K", "M", "DS", "LS", "MK", "A")
_POWER_NAME = re.compile(r"^(A|D|P)?(GND|VSS|VCC|VDD|VEE|VBAT|VIN|VBUS|VSYS|VREF)\w*$|^[+-]|^\d+V\d*$|V\d", re.I)
_GROUND = re.compile(r"^(A|D|P)?(GND|VSS)\w*$", re.I)
_PREFIX = re.compile(r"^#?([A-Za-z]+)")


def prefix(reference: str) -> str:
    found = _PREFIX.match(reference)
    return found.group(1).upper() if found else ""


def is_anchor(reference: str) -> bool:
    return prefix(reference) in ANCHOR_PREFIXES


def is_power_net(net: dict) -> bool:
    if _POWER_NAME.search(str(net.get("name") or "")):
        return True
    return any(node.get("pintype") in ("power_in", "power_out") for node in net.get("nodes") or [])


def auto_groups(components: list[dict], nets: list[dict]) -> list[dict]:
    """Agrupa cada pasivo con el integrado o conector al que sirve.

    components: [{reference, value}]. nets: [{name, nodes: [{ref, pin, pintype}]}].
    """
    order = [str(item["reference"]) for item in components]
    values = {str(item["reference"]): str(item.get("value") or "") for item in components}
    anchors = [ref for ref in order if is_anchor(ref)]
    if not anchors:
        return [{"name": "Circuito", "references": order}] if order else []

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
    pending = [ref for ref in order if ref not in group_of]
    for ref in pending:
        best = _best_anchor(ref, anchors, signal, members)
        if best:
            group_of[ref] = best

    changed = True
    while changed:
        changed = False
        for ref in pending:
            if ref in group_of:
                continue
            neighbours = [other for net in signal[ref] for other in members[net] if other != ref and other in group_of]
            if neighbours:
                group_of[ref] = group_of[neighbours[0]]
                changed = True

    for ref in pending:
        if ref in group_of:
            continue
        nets_here = [net for net in power[ref] if not _GROUND.match(net)]
        owner = next((driver for net in nets_here for driver in drivers.get(net, []) if driver in anchors), None)
        if owner is None:
            shared = [(sum(1 for net in nets_here if anchor in members[net]), anchor) for anchor in anchors]
            shared = [pair for pair in shared if pair[0] > 0]
            owner = max(shared, key=lambda pair: pair[0])[1] if shared else None
        if owner:
            group_of[ref] = owner

    groups = [
        {"name": f"{anchor} {values.get(anchor, '')}".strip(), "references": [ref for ref in order if group_of.get(ref) == anchor]}
        for anchor in anchors
    ]
    loose = [ref for ref in order if ref not in group_of]
    if loose:
        groups.append({"name": "Otros", "references": loose})
    return groups


def _best_anchor(ref: str, anchors: list[str], signal: dict[str, set[str]], members: dict[str, set[str]]) -> str | None:
    scores = []
    for anchor in anchors:
        count = sum(1 for net in signal[ref] if anchor in members[net])
        if count:
            scores.append((count, -anchors.index(anchor), anchor))
    return max(scores)[2] if scores else None


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
