"""Imágenes del esquemático y de la placa con kicad-cli, servidas en /renders."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VIEWS = ("schematic", "pcb", "pcb_3d", "pcb_3d_bottom", "pcb_3d_iso")
KEEP = 40
PCB_LAYERS = "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Fab,Edge.Cuts"


def renders_dir() -> Path:
    base = os.environ.get("KICAD_IA_CACHE")
    if base:
        root = Path(base)
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches" / "kicad-ia"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kicad-ia"
    path = root / "renders"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _target(view: str, suffix: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    return renders_dir() / f"{view}-{stamp}{suffix}"


def _prune() -> None:
    files = sorted(renders_dir().glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in files[KEEP:]:
        old.unlink(missing_ok=True)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)


def render_schematic(cli: str, schematic: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run([cli, "sch", "export", "svg", "--exclude-drawing-sheet", "-o", tmp, str(schematic)])
        produced = sorted(Path(tmp).glob("*.svg"))
        if not produced:
            return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "kicad-cli no generó el SVG."}
        root = next((path for path in produced if path.stem == schematic.stem), produced[0])
        target = _target("schematic", ".svg")
        target.write_bytes(root.read_bytes())
    _prune()
    return {"ok": True, "image": f"/renders/{target.name}", "format": "svg", "pages": len(produced)}


def render_board(cli: str, board_file: Path, view: str) -> dict:
    if view == "pcb":
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "board.svg"
            proc = _run(
                [
                    cli, "pcb", "export", "svg", "--mode-single", "--page-size-mode", "2", "--exclude-drawing-sheet",
                    "--layers", PCB_LAYERS, "-o", str(out), str(board_file),
                ]
            )
            if not out.is_file():
                return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "kicad-cli no generó el SVG."}
            target = _target("pcb", ".svg")
            target.write_bytes(out.read_bytes())
        _prune()
        return {"ok": True, "image": f"/renders/{target.name}", "format": "svg"}

    options = {
        "pcb_3d": ["--side", "top"],
        "pcb_3d_bottom": ["--side", "bottom"],
        "pcb_3d_iso": ["--side", "top", "--rotate", "-45,0,45", "--perspective"],
    }[view]
    target = _target(view, ".png")
    proc = _run([cli, "pcb", "render", "-w", "1400", "-h", "900", "--quality", "basic", *options, "-o", str(target), str(board_file)])
    if not target.is_file():
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "kicad-cli no generó la imagen 3D."}
    _prune()
    return {"ok": True, "image": f"/renders/{target.name}", "format": "png"}
