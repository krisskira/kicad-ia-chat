"""Llamadas a kicad-cli: ERC del esquemático y netlist."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from kicad_ia.kicad.sexpr import child, children, parse


def find_kicad_cli(configured: str = "") -> str | None:
    for candidate in (configured, os.environ.get("KICAD_CLI", "")):
        if candidate and Path(candidate).is_file():
            return candidate
    found = shutil.which("kicad-cli")
    if found:
        return found
    if sys.platform == "darwin":
        bundled = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
        if bundled.is_file():
            return str(bundled)
    return None


def run_erc(cli: str, schematic: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "erc.json"
        proc = subprocess.run(
            [cli, "sch", "erc", "--format", "json", "--severity-all", "-o", str(report), str(schematic)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if not report.is_file():
            return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "kicad-cli no generó el informe ERC."}
        data = json.loads(report.read_text(encoding="utf-8"))
    violations = []
    for sheet in data.get("sheets") or []:
        violations.extend(sheet.get("violations") or [])
    kinds: dict[str, int] = {}
    problems = []
    for violation in violations:
        kind = str(violation.get("type") or "")
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "pin_not_connected":
            continue
        items = [str(item.get("description") or "") for item in violation.get("items") or []]
        problems.append(f"{violation.get('severity')}: {violation.get('description')} — {'; '.join(items)}")
    unused = kinds.get("pin_not_connected", 0)
    if problems:
        verdict = f"El ERC no está limpio: {len(problems)} problemas además de {unused} pines sin usar."
    elif unused:
        verdict = f"Sin problemas de conexión. Quedan {unused} pines sin usar marcados como no conectados."
    else:
        verdict = "ERC limpio."
    return {"ok": True, "verdict": verdict, "by_type": kinds, "problems": problems[:20]}


def export_netlist(cli: str, schematic: Path, output: Path) -> dict:
    data = read_netlist(cli, schematic, output)
    if not data["ok"]:
        return data
    return {
        "ok": True,
        "netlist": str(output),
        "components": [comp["reference"] for comp in data["components"]],
        "nets": [{"name": net["name"], "nodes": len(net["nodes"])} for net in data["nets"]],
    }


def read_netlist(cli: str, schematic: Path, output: Path | None = None) -> dict:
    """Componentes y redes tal como los ve KiCad, sin las redes de pines sueltos."""
    with tempfile.TemporaryDirectory() as tmp:
        target = output or Path(tmp) / "kicad-ia.net"
        proc = subprocess.run(
            [cli, "sch", "export", "netlist", "-o", str(target), str(schematic)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0 or not target.is_file():
            return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "Falló la exportación del netlist."}
        root = parse(target.read_text(encoding="utf-8"))[0]
    components = []
    for comp in children(child(root, "components") or [], "comp"):
        source = child(comp, "libsource") or []
        lib, part = _text(child(source, "lib")), _text(child(source, "part"))
        components.append(
            {
                "reference": _text(child(comp, "ref")),
                "value": _text(child(comp, "value")),
                "footprint": _text(child(comp, "footprint")),
                "lib_id": f"{lib}:{part}" if lib and part else "",
            }
        )
    nets = []
    for net in children(child(root, "nets") or [], "net"):
        name = _text(child(net, "name")).lstrip("/")
        if name.startswith("unconnected-"):
            continue
        nodes = [
            {"ref": _text(child(node, "ref")), "pin": _text(child(node, "pin")), "pintype": _text(child(node, "pintype"))}
            for node in children(net, "node")
        ]
        nets.append({"name": name, "nodes": nodes})
    return {"ok": True, "components": components, "nets": nets}


def _text(node) -> str:
    return str(node[1]) if node and len(node) > 1 else ""


def run_drc(cli: str, board: Path, schematic_parity: bool = True) -> dict:
    """DRC de placa con kicad-cli. Devuelve conteos y problemas legibles."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "drc.json"
        args = [cli, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", str(report)]
        if schematic_parity:
            args.append("--schematic-parity")
        args.append(str(board))
        proc = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
        if not report.is_file():
            return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "kicad-cli no generó el informe DRC."}
        data = json.loads(report.read_text(encoding="utf-8"))
    violations = data.get("violations") or []
    if not violations:
        for sheet in data.get("sheets") or []:
            violations.extend(sheet.get("violations") or [])
    kinds: dict[str, int] = {}
    problems = []
    errors = warnings = 0
    unconnected = 0
    for violation in violations:
        kind = str(violation.get("type") or violation.get("description") or "other")
        severity = str(violation.get("severity") or "error").lower()
        kinds[kind] = kinds.get(kind, 0) + 1
        if "unconnected" in kind.lower() or "unrouted" in kind.lower():
            unconnected += 1
        if severity.startswith("warn"):
            warnings += 1
        else:
            errors += 1
        items = [str(item.get("description") or item.get("message") or "") for item in violation.get("items") or []]
        desc = str(violation.get("description") or violation.get("type") or kind)
        problems.append(f"{severity}: {desc}" + (f" — {'; '.join(i for i in items if i)}" if items else ""))
    if errors or unconnected:
        verdict = f"DRC con {errors} errores, {warnings} avisos y {unconnected} sin rutear."
    elif warnings:
        verdict = f"DRC sin errores duros; {warnings} avisos."
    else:
        verdict = "DRC limpio."
    return {
        "ok": True,
        "verdict": verdict,
        "error_count": errors,
        "warning_count": warnings,
        "unconnected": unconnected,
        "by_type": kinds,
        "problems": problems[:40],
    }
