"""Llama al Python incluido en KiCad para exportar/importar Specctra DSN/SES.

kicad-cli 10 no exporta DSN. pcbnew sí: ExportSpecctraDSN / ImportSpecctraSES.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

MAC_PCBNEW_PYTHON = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"


def find_pcbnew_python(configured: str = "") -> str | None:
    for candidate in (configured, os.environ.get("KICAD_PYTHON", "")):
        if candidate and Path(candidate).is_file():
            return candidate
    if sys.platform == "darwin" and Path(MAC_PCBNEW_PYTHON).is_file():
        return MAC_PCBNEW_PYTHON
    # En Linux a veces está en PATH como python3 de KiCad; no lo adivinamos.
    return None


def apply_fab_rules(board_file: Path, fab: dict, python_bin: str | None = None) -> dict:
    """Ajusta anchos/clearance/vías de diseño en una copia de placa antes del DSN."""
    py = python_bin or find_pcbnew_python()
    if not py:
        return {"ok": False, "error": "No encuentro el Python de KiCad (pcbnew). Define KICAD_PYTHON."}
    track = float(fab.get("min_track_mm") or 0.15)
    clearance = float(fab.get("min_clearance_mm") or 0.15)
    via_dia = float(fab.get("min_via_diameter_mm") or 0.6)
    via_drill = float(fab.get("min_via_drill_mm") or 0.3)
    hole = float(fab.get("min_hole_mm") or via_drill)
    script = textwrap.dedent(
        f"""
        import sys
        import pcbnew
        board = pcbnew.LoadBoard({str(board_file)!r})
        settings = board.GetDesignSettings()
        iu = pcbnew.FromMM
        settings.SetCustomTrackWidth(True)
        settings.SetTrackWidth(iu({track}))
        settings.SetMinTrackWidth(iu({track}))
        settings.m_MinClearance = iu({clearance})
        settings.m_TrackClearance = iu({clearance})
        settings.SetMinThroughDrill(iu({min(via_drill, hole)}))
        settings.SetViasMinSize(iu({via_dia}))
        settings.SetCustomViaSize(True)
        settings.SetViaSize(iu({via_dia}))
        settings.SetViaDrill(iu({via_drill}))
        try:
            settings.m_MinHole = iu({hole})
        except Exception:
            pass
        pcbnew.SaveBoard({str(board_file)!r}, board)
        sys.exit(0)
        """
    )
    proc = subprocess.run([py, "-c", script], capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout).strip() or "No pude aplicar las reglas de fabricación.",
        }
    return {
        "ok": True,
        "file": str(board_file),
        "fab": {
            "min_track_mm": track,
            "min_clearance_mm": clearance,
            "min_via_diameter_mm": via_dia,
            "min_via_drill_mm": via_drill,
            "min_hole_mm": hole,
        },
    }


def export_dsn(board_file: Path, dsn_file: Path, python_bin: str | None = None) -> dict:
    py = python_bin or find_pcbnew_python()
    if not py:
        return {"ok": False, "error": "No encuentro el Python de KiCad (pcbnew). Define KICAD_PYTHON."}
    script = textwrap.dedent(
        f"""
        import sys
        import pcbnew
        board = pcbnew.LoadBoard({str(board_file)!r})
        ok = pcbnew.ExportSpecctraDSN(board, {str(dsn_file)!r})
        sys.exit(0 if ok else 2)
        """
    )
    return _run(py, script, dsn_file, "No se generó el DSN.")


def import_ses(board_file: Path, ses_file: Path, output_file: Path | None = None, python_bin: str | None = None) -> dict:
    py = python_bin or find_pcbnew_python()
    if not py:
        return {"ok": False, "error": "No encuentro el Python de KiCad (pcbnew). Define KICAD_PYTHON."}
    out = output_file or board_file
    script = textwrap.dedent(
        f"""
        import sys
        import pcbnew
        board = pcbnew.LoadBoard({str(board_file)!r})
        ok = pcbnew.ImportSpecctraSES(board, {str(ses_file)!r})
        if not ok:
            sys.exit(2)
        pcbnew.SaveBoard({str(out)!r}, board)
        sys.exit(0)
        """
    )
    return _run(py, script, out, "No se importó el SES.")


def board_stats(board_file: Path, python_bin: str | None = None) -> dict:
    py = python_bin or find_pcbnew_python()
    if not py:
        return {"ok": False, "error": "No encuentro el Python de KiCad (pcbnew)."}
    script = textwrap.dedent(
        f"""
        import json, sys, pcbnew
        board = pcbnew.LoadBoard({str(board_file)!r})
        tracks = list(board.GetTracks())
        vias = [t for t in tracks if t.GetClass() == 'VIA']
        segs = [t for t in tracks if t.GetClass() != 'VIA']
        length = 0.0
        for t in segs:
            try:
                length += float(t.GetLength()) / 1e6
            except Exception:
                pass
        print(json.dumps({{
            "ok": True,
            "footprints": board.GetFootprintCount(),
            "tracks": len(segs),
            "vias": len(vias),
            "track_length_mm": round(length, 2),
        }}))
        """
    )
    proc = subprocess.run([py, "-c", script], capture_output=True, text=True, timeout=120, check=False)
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or "Falló board_stats."}
    import json

    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "error": f"Salida ilegible de pcbnew: {exc}"}


def _run(python_bin: str, script: str, expected: Path, missing: str) -> dict:
    proc = subprocess.run([python_bin, "-c", script], capture_output=True, text=True, timeout=180, check=False)
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip() or f"pcbnew falló ({proc.returncode})."}
    if not expected.is_file() or expected.stat().st_size < 8:
        return {"ok": False, "error": missing}
    return {"ok": True, "file": str(expected)}
