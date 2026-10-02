"""Las bibliotecas que KiCad tiene configuradas: sym-lib-table y fp-lib-table.

Se leen los mismos archivos que muestra el selector de símbolos de KiCad.
El índice se guarda en caché por ruta y fecha de modificación.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from kicad_ia.kicad.sexpr import Sym, child, children, head, number, parse

_VAR = re.compile(r"\$\{([^}]+)\}")
_TOKEN = re.compile(r"[a-z0-9]+")
_SYMBOL_LINE = re.compile(r'^(\s*)\(symbol "((?:[^"\\]|\\.)+)"')
_PROPERTY = re.compile(r'\(property "(Description|ki_description|ki_keywords|Footprint|Datasheet)" "((?:[^"\\]|\\.)*)"')
_EXTENDS = re.compile(r'\(extends "((?:[^"\\]|\\.)+)"\)')
_UNIT = re.compile(r"^(.*)_(\d+)_(\d+)$")


@dataclass
class LibraryRow:
    nickname: str
    path: Path
    kind: str
    description: str = ""


@dataclass
class KicadPaths:
    config_dir: Path | None
    share_dir: Path | None
    major: int
    variables: dict[str, str] = field(default_factory=dict)

    def expand(self, uri: str) -> str:
        def replace(match: re.Match) -> str:
            name = match.group(1)
            return self.variables.get(name) or os.environ.get(name) or match.group(0)

        expanded = uri
        for _ in range(4):
            new = _VAR.sub(replace, expanded)
            if new == expanded:
                break
            expanded = new
        return expanded


def _config_roots() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        return [home / "Library" / "Preferences" / "kicad"]
    if sys.platform.startswith("win"):
        return [Path(os.environ.get("APPDATA", home)) / "kicad"]
    return [Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "kicad"]


def _share_candidates() -> list[Path]:
    if os.environ.get("KICAD_SHARE"):
        return [Path(os.environ["KICAD_SHARE"])]
    if sys.platform == "darwin":
        return [Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")]
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "KiCad"
        return sorted(base.glob("*/share/kicad"), reverse=True)
    return [Path("/usr/share/kicad"), Path("/usr/local/share/kicad")]


def detect_paths(major: int | None = None, project_dir: Path | None = None) -> KicadPaths:
    config_dir = None
    for root in _config_roots():
        if not root.is_dir():
            continue
        versions = sorted(
            (path for path in root.iterdir() if path.is_dir() and re.fullmatch(r"\d+\.\d+", path.name)),
            key=lambda path: tuple(int(part) for part in path.name.split(".")),
        )
        preferred = [path for path in versions if major and path.name.split(".")[0] == str(major)]
        chosen = (preferred or versions)[-1:] if versions else []
        if chosen:
            config_dir = chosen[0]
            break
    if major is None and config_dir is not None:
        major = int(config_dir.name.split(".")[0])
    major = major or 10
    share_dir = next((path for path in _share_candidates() if path.is_dir()), None)

    variables: dict[str, str] = {}
    if share_dir is not None:
        for version in {major, major - 1, major - 2}:
            variables[f"KICAD{version}_SYMBOL_DIR"] = str(share_dir / "symbols")
            variables[f"KICAD{version}_FOOTPRINT_DIR"] = str(share_dir / "footprints")
            variables[f"KICAD{version}_3DMODEL_DIR"] = str(share_dir / "3dmodels")
            variables[f"KICAD{version}_TEMPLATE_DIR"] = str(share_dir / "template")
    if config_dir is not None:
        common = config_dir / "kicad_common.json"
        if common.is_file():
            try:
                data = json.loads(common.read_text(encoding="utf-8"))
                for name, value in ((data.get("environment") or {}).get("vars") or {}).items():
                    if isinstance(value, str) and value:
                        variables[name] = value
            except (OSError, json.JSONDecodeError):
                pass
    if project_dir is not None:
        variables["KIPRJMOD"] = str(project_dir)
    return KicadPaths(config_dir=config_dir, share_dir=share_dir, major=major, variables=variables)


def _read_table(path: Path, paths: KicadPaths, seen: set[Path]) -> list[LibraryRow]:
    if not path.is_file() or path in seen:
        return []
    seen.add(path)
    try:
        tree = parse(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows: list[LibraryRow] = []
    for table in tree:
        if not isinstance(table, list):
            continue
        for lib in children(table, "lib"):
            if child(lib, "disabled") is not None:
                continue
            name_node = child(lib, "name")
            uri_node = child(lib, "uri")
            type_node = child(lib, "type")
            if not name_node or not uri_node:
                continue
            nickname = str(name_node[1])
            uri = Path(paths.expand(str(uri_node[1])))
            kind = str(type_node[1]) if type_node and len(type_node) > 1 else "KiCad"
            descr_node = child(lib, "descr")
            description = str(descr_node[1]) if descr_node and len(descr_node) > 1 else ""
            if kind == "Table":
                rows.extend(_read_table(uri, paths, seen))
                continue
            rows.append(LibraryRow(nickname, uri, kind, description))
    return rows


def library_rows(table_name: str, paths: KicadPaths, project_dir: Path | None) -> list[LibraryRow]:
    rows: list[LibraryRow] = []
    seen: set[Path] = set()
    if project_dir is not None:
        rows.extend(_read_table(project_dir / table_name, paths, seen))
    if paths.config_dir is not None:
        rows.extend(_read_table(paths.config_dir / table_name, paths, seen))
    unique: dict[str, LibraryRow] = {}
    for row in rows:
        unique.setdefault(row.nickname, row)
    return list(unique.values())


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _compact(text: str) -> str:
    return "".join(tokens(text))


def score(query: str, name: str, extra: str) -> int:
    wanted = tokens(query)
    if not wanted:
        return 1
    name_tokens = set(tokens(name))
    haystack = (name + " " + extra).casefold()
    total = 0
    for token in wanted:
        if token in name_tokens:
            total += 3
        elif token in haystack:
            total += 1
    compact_query = _compact(query)
    compact_name = _compact(name)
    if compact_query and compact_query == compact_name:
        total += 10
    elif compact_name and compact_query.startswith(compact_name):
        total += 6
    elif compact_query and compact_query in compact_name:
        total += 4
    minimum = max(1, (len(wanted) + 1) // 2)
    return total if total >= minimum else 0


def _unescape(text: str) -> str:
    return text.replace('\\"', '"').replace("\\\\", "\\")


def scan_symbol_file(path: Path) -> list[dict]:
    entries: list[dict] = []
    top_indent: str | None = None
    current: dict | None = None
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    with handle:
        for line in handle:
            match = _SYMBOL_LINE.match(line)
            if match:
                indent, name = match.group(1), _unescape(match.group(2))
                if top_indent is None:
                    top_indent = indent
                if indent == top_indent:
                    current = {"name": name, "description": "", "keywords": "", "footprint": "", "datasheet": "", "extends": ""}
                    entries.append(current)
                    rest = line[match.end():]
                else:
                    continue
            else:
                rest = line
            if current is None:
                continue
            for prop in _PROPERTY.finditer(rest):
                key, value = prop.group(1), _unescape(prop.group(2))
                if key in ("Description", "ki_description") and not current["description"]:
                    current["description"] = value
                elif key == "ki_keywords":
                    current["keywords"] = value
                elif key == "Footprint" and not current["footprint"]:
                    current["footprint"] = value
                elif key == "Datasheet" and not current["datasheet"]:
                    current["datasheet"] = value
            extends = _EXTENDS.search(rest)
            if extends:
                current["extends"] = _unescape(extends.group(1))
    return entries


def _cache_dir() -> Path:
    base = os.environ.get("KICAD_IA_CACHE")
    if base:
        return Path(base)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "kicad-ia"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kicad-ia"


class LibraryIndex:
    def __init__(self, paths: KicadPaths, project_dir: Path | None = None) -> None:
        self.paths = paths
        self.project_dir = project_dir
        self.symbol_libs = [row for row in library_rows("sym-lib-table", paths, project_dir) if row.path.suffix == ".kicad_sym"]
        self.footprint_libs = [row for row in library_rows("fp-lib-table", paths, project_dir) if row.path.suffix == ".pretty"]
        self._symbols: list[dict] | None = None
        self._footprints: list[dict] | None = None

    def summary(self) -> dict:
        return {
            "config_dir": str(self.paths.config_dir or ""),
            "share_dir": str(self.paths.share_dir or ""),
            "symbol_libraries": len(self.symbol_libs),
            "footprint_libraries": len(self.footprint_libs),
        }

    def symbols(self) -> list[dict]:
        if self._symbols is not None:
            return self._symbols
        cache_file = _cache_dir() / ("symbols-" + hashlib.sha1(
            "|".join(f"{row.nickname}={row.path}" for row in self.symbol_libs).encode()
        ).hexdigest()[:12] + ".json")
        cached: dict = {}
        if cache_file.is_file():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = {}
        fresh: dict = {}
        entries: list[dict] = []
        for row in self.symbol_libs:
            try:
                stat = row.path.stat()
            except OSError:
                continue
            stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
            record = cached.get(str(row.path))
            if not record or record.get("stamp") != stamp:
                record = {"stamp": stamp, "entries": scan_symbol_file(row.path)}
            fresh[str(row.path)] = record
            for entry in record["entries"]:
                entries.append({**entry, "lib": row.nickname, "lib_id": f"{row.nickname}:{entry['name']}"})
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(fresh), encoding="utf-8")
        except OSError:
            pass
        self._symbols = entries
        return entries

    def footprints(self) -> list[dict]:
        if self._footprints is not None:
            return self._footprints
        entries = []
        for row in self.footprint_libs:
            if not row.path.is_dir():
                continue
            for item in sorted(row.path.glob("*.kicad_mod")):
                entries.append({"lib": row.nickname, "name": item.stem, "lib_id": f"{row.nickname}:{item.stem}", "path": str(item)})
        self._footprints = entries
        return entries

    def search_symbols(self, query: str, limit: int = 20) -> list[dict]:
        ranked = []
        for entry in self.symbols():
            value = score(query, entry["name"], f"{entry['lib']} {entry['description']} {entry['keywords']}")
            if value:
                ranked.append((value, entry))
        ranked.sort(key=lambda pair: (-pair[0], len(pair[1]["name"]), pair[1]["lib_id"]))
        return [
            {
                "lib_id": entry["lib_id"],
                "description": entry["description"],
                "keywords": entry["keywords"],
                "footprint": entry["footprint"],
                "datasheet": entry["datasheet"],
            }
            for _, entry in ranked[:limit]
        ]

    def search_footprints(self, query: str, limit: int = 20) -> list[dict]:
        ranked = []
        for entry in self.footprints():
            value = score(query, entry["name"], entry["lib"])
            if value:
                ranked.append((value, entry))
        ranked.sort(key=lambda pair: (-pair[0], len(pair[1]["name"]), pair[1]["lib_id"]))
        return [{"lib_id": entry["lib_id"]} for _, entry in ranked[:limit]]

    def symbol_row(self, nickname: str) -> LibraryRow | None:
        return next((row for row in self.symbol_libs if row.nickname == nickname), None)

    def footprint_row(self, nickname: str) -> LibraryRow | None:
        return next((row for row in self.footprint_libs if row.nickname == nickname), None)

    def load_symbol(self, lib_id: str) -> list | None:
        nickname, _, name = lib_id.partition(":")
        row = self.symbol_row(nickname)
        if row is None or not name:
            return None
        try:
            text = row.path.read_text(encoding="utf-8")
        except OSError:
            return None
        return flatten_symbol(text, name)

    def describe_symbol(self, lib_id: str) -> dict | None:
        node = self.load_symbol(lib_id)
        if node is None:
            return None
        return symbol_summary(lib_id, node)

    def describe_footprint(self, lib_id: str) -> dict | None:
        nickname, _, name = lib_id.partition(":")
        row = self.footprint_row(nickname)
        if row is None:
            return None
        path = row.path / f"{name}.kicad_mod"
        if not path.is_file():
            return None
        try:
            tree = parse(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        root = tree[0] if tree and isinstance(tree[0], list) else []
        descr = child(root, "descr")
        attr = child(root, "attr")
        pads = children(root, "pad")
        models = []
        for model in children(root, "model"):
            raw = str(model[1]) if len(model) > 1 else ""
            resolved = self.paths.expand(raw)
            models.append({"path": raw, "resolved": resolved, "exists": Path(resolved).is_file()})
        return {
            "lib_id": lib_id,
            "description": str(descr[1]) if descr and len(descr) > 1 else "",
            "mounting": str(attr[1]) if attr and len(attr) > 1 else "",
            "pad_count": len({str(pad[1]) for pad in pads if len(pad) > 1 and str(pad[1])}),
            "models": models,
        }


def _block_end(text: str, start: int) -> int:
    depth = 0
    i = start
    in_string = False
    while i < len(text):
        c = text[i]
        if in_string:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _symbol_block(text: str, name: str) -> list | None:
    pattern = re.compile(r'^(\s*)\(symbol "' + re.escape(name.replace('"', '\\"')) + r'"', re.M)
    first = re.search(r'^(\s*)\(symbol "', text, re.M)
    top_indent = first.group(1) if first else None
    for match in pattern.finditer(text):
        if top_indent is not None and match.group(1) != top_indent:
            continue
        start = match.start() + len(match.group(1))
        end = _block_end(text, start)
        tree = parse(text[start:end])
        return tree[0] if tree else None
    return None


def flatten_symbol(text: str, name: str, depth: int = 0) -> list | None:
    node = _symbol_block(text, name)
    if node is None or depth > 5:
        return node
    extends = child(node, "extends")
    if extends is None:
        return node
    parent = flatten_symbol(text, str(extends[1]), depth + 1)
    if parent is None:
        return node
    parent_name = str(parent[1])
    merged = copy.deepcopy(parent)
    merged[1] = name
    own_props = {str(prop[1]): prop for prop in children(node, "property")}
    rebuilt: list = [merged[0], name]
    for item in merged[2:]:
        if head(item) == "property" and str(item[1]) in own_props:
            rebuilt.append(own_props.pop(str(item[1])))
        elif head(item) == "symbol":
            sub = copy.deepcopy(item)
            sub_name = str(sub[1])
            if sub_name.startswith(parent_name + "_"):
                sub[1] = name + sub_name[len(parent_name):]
            rebuilt.append(sub)
        else:
            rebuilt.append(item)
    insert_at = next((i for i, item in enumerate(rebuilt) if head(item) == "symbol"), len(rebuilt))
    for prop in own_props.values():
        rebuilt.insert(insert_at, prop)
        insert_at += 1
    for item in node[2:]:
        if head(item) in ("property", "extends", "symbol"):
            continue
        key = head(item)
        rebuilt = [existing for existing in rebuilt if head(existing) != key] if key else rebuilt
        rebuilt.insert(2, item)
    return rebuilt


def _is_hidden(node: list) -> bool:
    if Sym("hide") in node:
        return True
    hide = child(node, "hide")
    return hide is not None and (len(hide) == 1 or str(hide[1]) == "yes")


_OUTWARD = {0: "left", 90: "down", 180: "right", 270: "up"}


def symbol_pins(node: list) -> list[dict]:
    pins = []
    for sub in children(node, "symbol"):
        match = _UNIT.match(str(sub[1]))
        unit = int(match.group(2)) if match else 1
        style = int(match.group(3)) if match else 1
        if style not in (0, 1):
            continue
        for pin in children(sub, "pin"):
            at = child(pin, "at")
            if at is None:
                continue
            pin_name = child(pin, "name")
            pin_number = child(pin, "number")
            angle = int(round(number(at[3]) if len(at) > 3 else 0)) % 360
            pins.append(
                {
                    "number": str(pin_number[1]) if pin_number else "",
                    "name": str(pin_name[1]) if pin_name else "",
                    "type": str(pin[1]) if len(pin) > 1 else "",
                    "unit": unit,
                    "x_mm": number(at[1]),
                    "y_mm": -number(at[2]),
                    "outward": _OUTWARD.get(angle, "left"),
                    "hidden": _is_hidden(pin),
                }
            )
    return pins


def symbol_summary(lib_id: str, node: list) -> dict:
    props = {str(prop[1]): str(prop[2]) for prop in children(node, "property") if len(prop) > 2}
    pins = symbol_pins(node)
    units = sorted({pin["unit"] for pin in pins if pin["unit"]}) or [1]
    visible = [pin for pin in pins if not pin["hidden"]]
    xs = [pin["x_mm"] for pin in visible] or [0.0]
    ys = [pin["y_mm"] for pin in visible] or [0.0]
    return {
        "lib_id": lib_id,
        "reference_prefix": props.get("Reference", "U"),
        "value": props.get("Value", ""),
        "footprint": props.get("Footprint", ""),
        # Patrones del símbolo (R_*, SOT?23*). Sirven para buscar huellas
        # cuando la biblioteca no trae una por defecto, como Device:R.
        "footprint_filters": props.get("ki_fp_filters", "").split(),
        "datasheet": props.get("Datasheet", ""),
        "description": props.get("Description", props.get("ki_description", "")),
        "units": units,
        "power_symbol": child(node, "power") is not None,
        "size_mm": {"width": round(max(xs) - min(xs), 2), "height": round(max(ys) - min(ys), 2)},
        "pins": [
            {key: pin[key] for key in ("number", "name", "type", "unit", "outward")}
            for pin in visible
        ],
    }
