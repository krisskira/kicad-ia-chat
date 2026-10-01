"""Importa símbolo, huella y 3D de LCSC/EasyEDA a la biblioteca del proyecto."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

from kicad_ia.kicad.libraries import scan_symbol_file
from kicad_ia.kicad.sexpr import Sym, child, children, dumps, parse

LIB_NAME = "kicad-ia"
_LCSC = re.compile(r"C\d+")
_IMPORT_LOCK = threading.Lock()


def search_lcsc(query: str, limit: int = 8) -> dict:
    try:
        from easyeda2kicad.easyeda.easyeda_api import EasyedaApi
    except ImportError:
        return {"ok": False, "error": "Falta easyeda2kicad. Instálalo con pip install easyeda2kicad."}
    found = EasyedaApi().search_jlcpcb_components(query, page_size=max(1, min(limit, 20)))
    matches = [
        {
            "lcsc": item.get("lcsc", ""),
            "name": item.get("name", ""),
            "model": item.get("model", ""),
            "brand": item.get("brand", ""),
            "package": item.get("package", ""),
            "stock": item.get("stock", 0),
            "description": item.get("description", ""),
        }
        for item in found.get("results") or []
    ]
    ordered = sorted(matches, key=lambda item: str(item["lcsc"]).startswith("C9900"))
    result = {"ok": True, "query": query, "matches": ordered[:limit]}
    if not ordered:
        result["note"] = "LCSC no tiene resultados. Habrá que crearla desde el datasheet o usar un conector genérico."
    else:
        result["note"] = "Enseña estas opciones al usuario y espera a que elija un código C antes de import_lcsc."
        if any(str(item["lcsc"]).startswith("C9900") for item in ordered[:limit]):
            result["note"] += " Los códigos C9900 son de JLCPCB Assembly y casi nunca traen símbolo ni huella."
    return result


def import_lcsc(project_dir: Path, lcsc_id: str, runner=None) -> dict:
    code = lcsc_id.strip().upper()
    if not _LCSC.fullmatch(code):
        return {"ok": False, "error": "El código LCSC tiene la forma C seguido de números, por ejemplo C2040."}
    symbol_file = project_dir / f"{LIB_NAME}.kicad_sym"
    before = {entry["name"] for entry in scan_symbol_file(symbol_file)} if symbol_file.is_file() else set()
    status = (runner or _run_easyeda)(project_dir, code)
    if status == 2:
        return {"ok": False, "error": "Falta easyeda2kicad. Instálalo con pip install easyeda2kicad."}
    if status != 0 or not symbol_file.is_file():
        return {
            "ok": False,
            "error": (
                f"EasyEDA no publica el CAD de {code}. "
                "Prueba otro código de la lista; los C9900 de JLCPCB Assembly no traen símbolo."
            ),
        }
    register_project_library(project_dir)
    name = _symbol_with_lcsc(symbol_file, code)
    if name is None:
        added = [entry["name"] for entry in scan_symbol_file(symbol_file) if entry["name"] not in before]
        name = added[-1] if added else ""
    fields = _fields(symbol_file, name) if name else {}
    models = list((project_dir / f"{LIB_NAME}.3dshapes").glob("*"))
    return {
        "ok": bool(name),
        "lcsc": code,
        "lib_id": f"{LIB_NAME}:{name}" if name else "",
        "footprint": fields.get("Footprint", ""),
        "models": [path.name for path in models],
        "library": str(symbol_file),
        "error": "" if name else f"Se descargó {code} pero no encuentro el símbolo en la biblioteca.",
    }


def register_project_library(project_dir: Path) -> None:
    _ensure_row(project_dir, "sym-lib-table", "sym_lib_table", "${KIPRJMOD}/kicad-ia.kicad_sym")
    _ensure_row(project_dir, "fp-lib-table", "fp_lib_table", "${KIPRJMOD}/kicad-ia.pretty")


def _ensure_row(project_dir: Path, filename: str, root_name: str, uri: str) -> None:
    path = project_dir / filename
    if path.is_file():
        tree = parse(path.read_text(encoding="utf-8"))[0]
    else:
        tree = [Sym(root_name), [Sym("version"), 7]]
    for lib in children(tree, "lib"):
        name = child(lib, "name")
        if name and str(name[1]) == LIB_NAME:
            uri_node = child(lib, "uri")
            if uri_node is not None:
                uri_node[1] = uri
            path.write_text(dumps(tree) + "\n", encoding="utf-8")
            return
    tree.append(
        [
            Sym("lib"),
            [Sym("name"), LIB_NAME],
            [Sym("type"), "KiCad"],
            [Sym("uri"), uri],
            [Sym("options"), ""],
            [Sym("descr"), "Piezas importadas por KiCad IA desde LCSC"],
        ]
    )
    path.write_text(dumps(tree) + "\n", encoding="utf-8")


def _fields(path: Path, name: str) -> dict[str, str]:
    try:
        tree = parse(path.read_text(encoding="utf-8"))[0]
    except (OSError, ValueError):
        return {}
    for symbol in children(tree, "symbol"):
        if len(symbol) > 1 and str(symbol[1]) == name:
            return {str(prop[1]): str(prop[2]) for prop in children(symbol, "property") if len(prop) > 2}
    return {}


def _symbol_with_lcsc(path: Path, lcsc_id: str) -> str | None:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    current = ""
    top_indent: str | None = None
    for index, line in enumerate(lines):
        match = re.match(r'^(\s*)\(symbol "((?:[^"\\]|\\.)+)"', line)
        if match:
            indent, name = match.group(1), match.group(2)
            if top_indent is None or len(indent) <= len(top_indent):
                top_indent = indent
                current = name
        window = " ".join(lines[index:index + 4])
        found = re.search(r'\(property\s+"LCSC"\s+"((?:[^"\\]|\\.)*)"', window)
        if found and found.group(1) == lcsc_id and current:
            return current
    return None


def _run_easyeda(project_dir: Path, lcsc_id: str) -> int:
    try:
        from easyeda2kicad.__main__ import main
    except ImportError:
        return 2
    project_dir = project_dir.resolve()
    with _IMPORT_LOCK:
        previous = Path.cwd()
        try:
            os.chdir(project_dir)
            return main(
                [
                    "--lcsc_id",
                    lcsc_id,
                    "--full",
                    "--overwrite",
                    "--project-relative",
                    "--output",
                    str(project_dir / LIB_NAME),
                    "--custom-field",
                    f"LCSC:{lcsc_id}",
                ]
            )
        except Exception as exc:
            print(f"easyeda2kicad: {exc}")
            return 1
        finally:
            os.chdir(previous)
