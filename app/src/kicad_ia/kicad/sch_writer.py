"""Escribe símbolos de biblioteca, cables y etiquetas en un .kicad_sch.

KiCad 10 no tiene API de esquemático. Cada red se dibuja como un tramo corto
desde el pin y una etiqueta local con el nombre de la red: no hay cables largos
que se crucen por accidente.
"""

from __future__ import annotations

import copy
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from kicad_ia.kicad.geometry import SCH_GRID_MM, snap_mm
from kicad_ia.kicad.layout import Box, group_layout, normalize_groups
from kicad_ia.kicad.libraries import LibraryIndex, symbol_pins
from kicad_ia.kicad.sexpr import Sym, child, children, dumps, head, number, parse

STUB_MM = 2.54
_REF = re.compile(r"^(#?[A-Za-z_]+)(\d+)$")
_DIRECTION = {"left": (-1.0, 0.0, 180), "right": (1.0, 0.0, 0), "up": (0.0, -1.0, 90), "down": (0.0, 1.0, 270)}


class SchematicLocked(RuntimeError):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _at(x: float, y: float, angle: float = 0) -> list:
    return [Sym("at"), round(x, 4), round(y, 4), angle]


def _effects() -> list:
    return [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]


@dataclass
class PlacedPart:
    reference: str
    lib_id: str
    value: str
    footprint: str
    x_mm: float
    y_mm: float
    pins: list[dict] = field(default_factory=list)

    def pin(self, number_text: str) -> dict | None:
        for pin in self.pins:
            if pin["number"] == number_text:
                return pin
        for pin in self.pins:
            if pin["name"].casefold() == number_text.casefold():
                return pin
        return None

    def as_dict(self) -> dict:
        return {
            "reference": self.reference,
            "lib_id": self.lib_id,
            "value": self.value,
            "footprint": self.footprint,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
        }


def lock_file(path: Path) -> Path:
    return path.with_name(f"~{path.name}.lck")


def nets_from_connections(connections: list[dict]) -> list[dict]:
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for connection in connections:
        left = (str(connection.get("from_reference") or ""), str(connection.get("from_pin") or ""))
        right = (str(connection.get("to_reference") or ""), str(connection.get("to_pin") or ""))
        parent[find(left)] = find(right)
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for key in list(parent):
        groups.setdefault(find(key), []).append(key)
    nets = []
    for members in groups.values():
        members.sort()
        ref, pin = members[0]
        nets.append({"name": f"Net-{ref}-{pin}", "pins": [{"reference": r, "pin": p} for r, p in members]})
    return nets


class SchematicDocument:
    def __init__(self, path: Path, index: LibraryIndex) -> None:
        self.path = path
        self.index = index
        self.tree = parse(path.read_text(encoding="utf-8"))[0]
        self.root_uuid = str((child(self.tree, "uuid") or [None, _uuid()])[1])
        self.project = path.stem
        pro = next(path.parent.glob("*.kicad_pro"), None)
        if pro is not None:
            self.project = pro.stem

    def references(self) -> set[str]:
        found = set()
        for symbol in children(self.tree, "symbol"):
            for prop in children(symbol, "property"):
                if len(prop) > 2 and str(prop[1]) == "Reference":
                    found.add(str(prop[2]))
        return found

    def next_reference(self, prefix: str, taken: set[str]) -> str:
        prefix = prefix.rstrip("?") or "U"
        number_value = 1
        while f"{prefix}{number_value}" in taken:
            number_value += 1
        return f"{prefix}{number_value}"

    def _lib_symbols(self) -> list:
        node = child(self.tree, "lib_symbols")
        if node is None:
            node = [Sym("lib_symbols")]
            insert_at = next((i for i, item in enumerate(self.tree) if head(item) == "paper"), 3) + 1
            self.tree.insert(insert_at, node)
        return node

    def ensure_lib_symbol(self, lib_id: str, definition: list) -> None:
        holder = self._lib_symbols()
        if any(len(item) > 1 and str(item[1]) == lib_id for item in children(holder, "symbol")):
            return
        embedded = copy.deepcopy(definition)
        embedded[1] = lib_id
        embedded = [item for item in embedded if head(item) != "extends"]
        holder.append(embedded)

    def _insert(self, node: list) -> None:
        anchor = next((i for i, item in enumerate(self.tree) if head(item) == "sheet_instances"), len(self.tree))
        self.tree.insert(anchor, node)

    def add_symbol(self, lib_id: str, definition: list, reference: str, value: str, footprint: str, x: float, y: float) -> PlacedPart:
        self.ensure_lib_symbol(lib_id, definition)
        props = {str(prop[1]): prop for prop in children(definition, "property") if len(prop) > 2}
        overrides = {"Reference": reference}
        if value:
            overrides["Value"] = value
        if footprint:
            overrides["Footprint"] = footprint
        node: list = [
            Sym("symbol"),
            [Sym("lib_id"), lib_id],
            _at(x, y, 0),
            [Sym("unit"), 1],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes")],
            [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("no")],
            [Sym("uuid"), _uuid()],
        ]
        for name, prop in props.items():
            if name.startswith("ki_"):
                continue
            copied = copy.deepcopy(prop)
            if name in overrides:
                copied[2] = overrides[name]
            at = child(copied, "at")
            if at is not None and len(at) >= 3:
                at[1] = round(x + number(at[1]), 4)
                at[2] = round(y - number(at[2]), 4)
            node.append(copied)
        for missing in ("Reference", "Value", "Footprint"):
            if missing not in props and missing in overrides:
                node.append([Sym("property"), missing, overrides[missing], _at(x, y), _effects()])
        pins = [pin for pin in symbol_pins(definition) if pin["unit"] in (0, 1)]
        for number_text in dict.fromkeys(pin["number"] for pin in pins if pin["number"]):
            node.append([Sym("pin"), number_text, [Sym("uuid"), _uuid()]])
        node.append(
            [
                Sym("instances"),
                [Sym("project"), self.project, [Sym("path"), f"/{self.root_uuid}", [Sym("reference"), reference], [Sym("unit"), 1]]],
            ]
        )
        self._insert(node)
        placed = []
        for pin in pins:
            placed.append({**pin, "x_abs": snap_mm(x + pin["x_mm"]), "y_abs": snap_mm(y + pin["y_mm"])})
        return PlacedPart(reference, lib_id, value or str((props.get("Value") or [None, None, ""])[2]), footprint, x, y, placed)

    def add_net_stub(self, pin: dict, net: str) -> dict:
        dx, dy, angle = _DIRECTION.get(pin.get("outward", "left"), _DIRECTION["left"])
        x0, y0 = pin["x_abs"], pin["y_abs"]
        x1, y1 = snap_mm(x0 + dx * STUB_MM), snap_mm(y0 + dy * STUB_MM)
        self._insert(
            [
                Sym("wire"),
                [Sym("pts"), [Sym("xy"), x0, y0], [Sym("xy"), x1, y1]],
                [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                [Sym("uuid"), _uuid()],
            ]
        )
        justify = "right" if angle == 180 else "left"
        self._insert(
            [
                Sym("label"),
                net,
                _at(x1, y1, angle),
                [Sym("fields_autoplaced"), Sym("yes")],
                [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym(justify), Sym("bottom")]],
                [Sym("uuid"), _uuid()],
            ]
        )
        return {"net": net, "x1_mm": x0, "y1_mm": y0, "x2_mm": x1, "y2_mm": y1}

    def ensure_paper(self, paper: str) -> None:
        node = child(self.tree, "paper")
        current = str(node[1]) if node and len(node) > 1 else "A4"
        order = list(PAPER_MM)
        if current in order and order.index(current) >= order.index(paper):
            return
        if node is None:
            self.tree.insert(4, [Sym("paper"), paper])
        else:
            node[1:] = [paper]

    def add_group_frame(self, block: Box) -> None:
        x0, y0 = snap_mm(block.x), snap_mm(block.y)
        x1, y1 = snap_mm(block.x + block.width), snap_mm(block.y + block.height)
        self._insert(
            [
                Sym("rectangle"),
                [Sym("start"), x0, y0],
                [Sym("end"), x1, y1],
                [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("dash")]],
                [Sym("fill"), [Sym("type"), Sym("none")]],
                [Sym("uuid"), _uuid()],
            ]
        )
        self._insert(
            [
                Sym("text"),
                block.key,
                [Sym("exclude_from_sim"), Sym("no")],
                _at(x0 + 2.54, y0 + 5.08, 0),
                [Sym("effects"), [Sym("font"), [Sym("size"), 2, 2], [Sym("bold"), Sym("yes")]], [Sym("justify"), Sym("left"), Sym("bottom")]],
                [Sym("uuid"), _uuid()],
            ]
        )

    def clear(self) -> None:
        drawn = {"symbol", "wire", "label", "global_label", "junction", "no_connect", "bus", "bus_entry", "text", "rectangle"}
        self.tree[:] = [item for item in self.tree if head(item) not in drawn]
        holder = child(self.tree, "lib_symbols")
        if holder is not None:
            del holder[1:]

    def save(self) -> Path:
        backup_dir = self.path.parent / ".kicad-ia-backup"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / f"{self.path.stem}.{time.strftime('%Y%m%d-%H%M%S')}.kicad_sch"
        shutil.copy2(self.path, backup)
        self.path.write_text(dumps(self.tree) + "\n", encoding="utf-8")
        return backup


def read_symbols(path: Path) -> list[dict]:
    tree = parse(path.read_text(encoding="utf-8"))[0]
    rows = []
    for symbol in children(tree, "symbol"):
        lib = child(symbol, "lib_id")
        at = child(symbol, "at")
        props = {str(prop[1]): str(prop[2]) for prop in children(symbol, "property") if len(prop) > 2}
        rows.append(
            {
                "reference": props.get("Reference", ""),
                "value": props.get("Value", ""),
                "footprint": props.get("Footprint", ""),
                "lib_id": str(lib[1]) if lib else "",
                "x_mm": number(at[1]) if at else 0.0,
                "y_mm": number(at[2]) if at else 0.0,
            }
        )
    return rows


def set_footprint(path: Path, reference: str, footprint: str) -> dict:
    if lock_file(path).exists():
        raise SchematicLocked(f"{path.name} está abierto en el editor de esquemáticos. Ciérralo para cambiar la huella.")
    document = SchematicDocument(path, None)  # type: ignore[arg-type]
    for symbol in children(document.tree, "symbol"):
        props = {str(prop[1]): prop for prop in children(symbol, "property") if len(prop) > 2}
        if str((props.get("Reference") or [None, None, ""])[2]) != reference:
            continue
        if "Footprint" in props:
            props["Footprint"][2] = footprint
        else:
            at = child(symbol, "at") or _at(0, 0)
            symbol.insert(len(symbol) - 1, [Sym("property"), "Footprint", footprint, _at(number(at[1]), number(at[2])), _effects()])
        backup = document.save()
        return {"ok": True, "reference": reference, "footprint": footprint, "backup": str(backup)}
    return {"ok": False, "error": f"No hay ningún símbolo {reference} en {path.name}."}


PAPER_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0)}
LABEL_ROOM_MM = 22.86
TITLE_BLOCK_MM = 40.0


def auto_layout(sizes: list[dict], start=(25.4, 25.4), max_x=270.0) -> tuple[list[tuple[float, float]], float]:
    positions = []
    x, y = start
    row_height = 0.0
    for size in sizes:
        width = float(size.get("width") or 10.16) + 2 * LABEL_ROOM_MM
        height = float(size.get("height") or 10.16) + 2 * LABEL_ROOM_MM
        if x + width > max_x and positions:
            x = start[0]
            y += row_height
            row_height = 0.0
        positions.append((snap_mm(x + width / 2), snap_mm(y + height / 2)))
        x += width
        row_height = max(row_height, height)
    return positions, y + row_height


def layout_on_paper(sizes: list[dict], top: float = 25.4) -> tuple[str, list[tuple[float, float]]]:
    for paper, (width, height) in PAPER_MM.items():
        positions, bottom = auto_layout(sizes, start=(25.4, top), max_x=width - 25.4)
        if bottom <= height - TITLE_BLOCK_MM:
            return paper, positions
    return paper, positions


GROUP_PADDING_MM = 5.08
GROUP_HEADER_MM = 7.62


def grouped_layout_on_paper(
    sizes: dict[str, tuple[float, float]], groups: list[dict], top: float = 25.4
) -> tuple[str, dict[str, tuple[float, float]], list[Box]]:
    padded = {ref: (w + 2 * LABEL_ROOM_MM, h + 2 * LABEL_ROOM_MM) for ref, (w, h) in sizes.items()}
    for paper, (width, height) in PAPER_MM.items():
        centers, blocks, (_, used) = group_layout(
            padded, groups, max_width=width - 50.8, item_gap=2.54, group_gap=10.16,
            padding=GROUP_PADDING_MM, header=GROUP_HEADER_MM,
        )
        if top + used <= height - TITLE_BLOCK_MM:
            break
    shifted = {ref: (25.4 + x, top + y) for ref, (x, y) in centers.items()}
    for block in blocks:
        block.x += 25.4
        block.y += top
    return paper, shifted, blocks


def write_circuit(
    path: Path,
    index: LibraryIndex,
    symbols: list[dict],
    nets: list[dict],
    replace: bool = False,
    groups: list[dict] | None = None,
    check_power: bool = True,
) -> dict:
    if lock_file(path).exists():
        raise SchematicLocked(
            f"{path.name} está abierto en el editor de esquemáticos. Ciérralo para que pueda escribirlo; KiCad 10 no lo recarga solo."
        )
    document = SchematicDocument(path, index)
    if replace:
        document.clear()
    taken = document.references()
    errors: list[str] = []
    definitions = []
    for spec in symbols:
        lib_id = str(spec.get("lib_id") or "")
        definition = index.load_symbol(lib_id)
        if definition is None:
            errors.append(f"No está en las bibliotecas de KiCad: {lib_id}. Busca con search_parts.")
            continue
        footprint = str(spec.get("footprint") or "")
        if footprint and index.describe_footprint(footprint) is None:
            errors.append(f"{spec.get('reference')}: la huella {footprint} no está en las bibliotecas de KiCad. Búscala con search_parts kind=footprint.")
        definitions.append((spec, definition))
    errors.extend(_check_nets(definitions, nets, check_power))
    if errors:
        return {"ok": False, "written": False, "errors": errors}

    sizes = []
    offsets = []
    for spec, definition in definitions:
        pins = [pin for pin in symbol_pins(definition) if not pin["hidden"]]
        xs = [pin["x_mm"] for pin in pins] or [0.0]
        ys = [pin["y_mm"] for pin in pins] or [0.0]
        sizes.append({"width": max(xs) - min(xs), "height": max(ys) - min(ys)})
        offsets.append(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2))
    existing = [number(at[2]) for at in (child(symbol, "at") for symbol in children(document.tree, "symbol")) if at]
    top = max(existing) + 38.1 if existing else 25.4
    blocks: list[Box] = []
    if groups:
        refs = [str(spec.get("reference") or "") for spec, _ in definitions]
        clean, _ = normalize_groups(groups, refs)
        size_by_ref = {ref: (size["width"], size["height"]) for ref, size in zip(refs, sizes)}
        paper, centers, blocks = grouped_layout_on_paper(size_by_ref, clean, top)
        layout = [
            (snap_mm(centers[ref][0] - dx), snap_mm(centers[ref][1] - dy))
            for ref, (dx, dy) in zip(refs, offsets)
        ]
    else:
        paper, layout = layout_on_paper(sizes, top)
    document.ensure_paper(paper)
    for block in blocks:
        document.add_group_frame(block)

    placed: dict[str, PlacedPart] = {}
    for (spec, definition), auto in zip(definitions, layout):
        props = {str(prop[1]): str(prop[2]) for prop in children(definition, "property") if len(prop) > 2}
        reference = str(spec.get("reference") or "")
        if not reference or reference in taken:
            if reference in taken:
                errors.append(f"{reference} ya existía; se usa otra referencia.")
            reference = document.next_reference(props.get("Reference", "U"), taken)
        taken.add(reference)
        if spec.get("x_mm") is not None and spec.get("y_mm") is not None:
            x, y = snap_mm(spec["x_mm"]), snap_mm(spec["y_mm"])
        else:
            x, y = auto
        part = document.add_symbol(
            str(spec["lib_id"]),
            definition,
            reference,
            str(spec.get("value") or ""),
            str(spec.get("footprint") or ""),
            x,
            y,
        )
        placed[spec.get("reference") or reference] = part
        placed[reference] = part

    stubs = []
    used: set[tuple[str, str]] = set()
    pin_types: dict[str, set[str]] = {}
    for net in nets:
        name = str(net.get("name") or "").strip()
        if not name:
            errors.append("Una red no tiene nombre.")
            continue
        for member in net.get("pins") or []:
            reference = str(member.get("reference") or "")
            pin_id = str(member.get("pin") or "")
            part = placed.get(reference)
            if part is None:
                errors.append(f"Red {name}: {reference} no se colocó en esta operación.")
                continue
            pin = part.pin(pin_id)
            if pin is None:
                errors.append(f"Red {name}: {reference} no tiene el pin {pin_id}.")
                continue
            stubs.append(document.add_net_stub(pin, name))
            used.add((part.reference, pin["number"]))
            pin_types.setdefault(name, set()).add(pin["type"])

    unique = {part.reference: part for part in placed.values()}
    below = max((block.y + block.height for block in blocks), default=0.0)
    flags = _add_power_flags(document, index, pin_types, list(unique.values()), taken, below)
    unconnected = {
        part.reference: [pin["name"] if pin["name"] != "~" else pin["number"] for pin in part.pins if not pin["hidden"] and (part.reference, pin["number"]) not in used]
        for part in unique.values()
    }
    backup = document.save()
    return {
        "ok": not errors,
        "written": True,
        "file": str(path),
        "backup": str(backup),
        "placed": [part.as_dict() for part in unique.values()],
        "net_stubs": len(stubs),
        "power_flags": flags,
        "unconnected_pins": {ref: pins for ref, pins in unconnected.items() if pins},
        "errors": errors,
        "grid_mm": SCH_GRID_MM,
    }


def _find_pin(pins: list[dict], pin_id: str) -> dict | None:
    return next((pin for pin in pins if pin["number"] == pin_id), None) or next(
        (pin for pin in pins if pin["name"].casefold() == pin_id.casefold()), None
    )


def _check_nets(definitions: list[tuple[dict, list]], nets: list[dict], check_power: bool = True) -> list[str]:
    pins_by_ref = {
        str(spec.get("reference") or ""): [pin for pin in symbol_pins(definition) if pin["unit"] in (0, 1)]
        for spec, definition in definitions
    }
    errors: list[str] = []
    used: set[tuple[str, str]] = set()
    for net in nets:
        name = net.get("name")
        members = net.get("pins") or []
        if len(members) < 2:
            errors.append(f"La red {name} solo tiene {len(members)} pin; una señal necesita sus dos extremos.")
        for member in members:
            reference = str(member.get("reference") or "")
            pin_id = str(member.get("pin") or "")
            pins = pins_by_ref.get(reference)
            if pins is None:
                errors.append(f"Red {name}: {reference} no está entre los símbolos de esta operación.")
                continue
            pin = _find_pin(pins, pin_id)
            if pin is None:
                known = ", ".join(f"{p['number']}={p['name']}" for p in pins[:12])
                errors.append(f"Red {name}: {reference} no tiene el pin {pin_id}. Pines: {known}.")
                continue
            used.add((reference, pin["number"]))
    for reference, pins in pins_by_ref.items() if check_power else ():
        for pin in pins:
            if pin["type"] == "power_in" and not pin["hidden"] and (reference, pin["number"]) not in used:
                errors.append(f"{reference}: el pin de alimentación {pin['name']} ({pin['number']}) no está en ninguna red.")
    return list(dict.fromkeys(errors))


def _add_power_flags(
    document: SchematicDocument,
    index: LibraryIndex,
    pin_types: dict[str, set[str]],
    parts: list[PlacedPart],
    taken: set[str],
    below: float = 0.0,
) -> list[str]:
    needy = [name for name, kinds in pin_types.items() if "power_in" in kinds and "power_out" not in kinds]
    definition = index.load_symbol("power:PWR_FLAG") if needy else None
    if definition is None:
        return []
    bottom = max(max((part.y_mm for part in parts), default=50.8) + 38.1, below + 15.24)
    left = min((part.x_mm for part in parts), default=50.8)
    for position, name in enumerate(needy):
        reference = document.next_reference("#FLG", taken)
        taken.add(reference)
        flag = document.add_symbol("power:PWR_FLAG", definition, reference, "PWR_FLAG", "", snap_mm(left + 15.24 * position), snap_mm(bottom))
        document.add_net_stub(flag.pins[0], name)
    return needy
