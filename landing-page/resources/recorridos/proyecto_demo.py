"""Proyecto de demostración para los recorridos: LED a 5 V por USB-C.

El esquemático lo escribe `write_circuit` del plugin con las bibliotecas de
KiCad 10. La placa la arma pcbnew y el ruteo es el de `route_board_files`
(FreeRouting 2.0.1). Las imágenes salen de kicad-cli. Nada se inventa a mano.

Desde la raíz del repositorio, con el entorno del plugin:

  PYTHONPATH=app/src app/.venv/bin/python landing-page/resources/recorridos/proyecto_demo.py

Deja todo en /tmp/kicad-ia-recorrido (o en --dir).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from kicad_ia.kicad.freerouting import route_board_files
from kicad_ia.kicad.libraries import LibraryIndex, detect_paths
from kicad_ia.kicad.pcbnew_bridge import board_stats, find_pcbnew_python
from kicad_ia.kicad.sch_writer import write_circuit

HERE = Path(__file__).resolve().parent
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
NAME = "led-usbc"

SYMBOLS = [
    {
        "reference": "J1",
        "lib_id": "Connector:USB_C_Receptacle_PowerOnly_6P",
        "value": "USB-C",
        "footprint": "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
    },
    {"reference": "R1", "lib_id": "Device:R", "value": "1k", "footprint": "Resistor_SMD:R_0805_2012Metric"},
    {"reference": "R2", "lib_id": "Device:R", "value": "5.1k", "footprint": "Resistor_SMD:R_0805_2012Metric"},
    {"reference": "R3", "lib_id": "Device:R", "value": "5.1k", "footprint": "Resistor_SMD:R_0805_2012Metric"},
    {"reference": "D1", "lib_id": "Device:LED", "value": "LED rojo", "footprint": "LED_SMD:LED_0805_2012Metric"},
]

NETS = [
    {"name": "VBUS", "pins": [{"reference": "J1", "pin": "A9"}, {"reference": "R1", "pin": "1"}]},
    {
        "name": "GND",
        "pins": [
            {"reference": "J1", "pin": "A12"},
            {"reference": "J1", "pin": "SH"},
            {"reference": "R2", "pin": "2"},
            {"reference": "R3", "pin": "2"},
            {"reference": "D1", "pin": "1"},
        ],
    },
    {"name": "CC1", "pins": [{"reference": "J1", "pin": "A5"}, {"reference": "R2", "pin": "1"}]},
    {"name": "CC2", "pins": [{"reference": "J1", "pin": "B5"}, {"reference": "R3", "pin": "1"}]},
    {"name": "LED_A", "pins": [{"reference": "R1", "pin": "2"}, {"reference": "D1", "pin": "2"}]},
]

# Posiciones de la propuesta, en mm desde la esquina del contorno.
BOARD = {
    "board": {"x": 100, "y": 100, "width": 32, "height": 22},
    "nets": ["VBUS", "GND", "CC1", "CC2", "LED_A"],
    "parts": [
        {
            "reference": "J1",
            "value": "USB-C",
            "footprint": "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
            "pads": {"A9": "VBUS", "B9": "VBUS", "A12": "GND", "B12": "GND", "SH": "GND", "A5": "CC1", "B5": "CC2"},
            "at": [5.2, 11, 270],
        },
        {"reference": "R2", "value": "5.1k", "footprint": "Resistor_SMD:R_0805_2012Metric", "pads": {"1": "CC1", "2": "GND"}, "at": [14, 6.5, 0]},
        {"reference": "R3", "value": "5.1k", "footprint": "Resistor_SMD:R_0805_2012Metric", "pads": {"1": "CC2", "2": "GND"}, "at": [14, 15.5, 0]},
        {"reference": "R1", "value": "1k", "footprint": "Resistor_SMD:R_0805_2012Metric", "pads": {"1": "VBUS", "2": "LED_A"}, "at": [21, 11, 0]},
        {"reference": "D1", "value": "LED rojo", "footprint": "LED_SMD:LED_0805_2012Metric", "pads": {"1": "GND", "2": "LED_A"}, "at": [27, 11, 180]},
    ],
}

FAB = {
    "min_track_mm": 0.25,
    "min_clearance_mm": 0.2,
    "min_via_diameter_mm": 0.6,
    "min_via_drill_mm": 0.3,
    "min_hole_mm": 0.3,
}

EMPTY_SCHEMATIC = """(kicad_sch
\t(version 20260306)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "{uuid}")
\t(paper "A4")
\t(lib_symbols)
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""


def run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"Falló {' '.join(args[:3])}: {proc.stderr or proc.stdout}")


def pcb_svg(board: Path, target: Path) -> None:
    # Página entera: tras F8 las huellas están fuera del contorno. capturas.py recorta al contenido.
    run([
        CLI, "pcb", "export", "svg", "--mode-single", "--page-size-mode", "1", "--exclude-drawing-sheet",
        "--layers", "F.Cu,B.Cu,F.SilkS,F.Fab,Edge.Cuts", "-o", str(target), str(board),
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("/tmp/kicad-ia-recorrido"))
    args = parser.parse_args()
    root = args.dir
    project = root / NAME
    renders = root / "renders"
    shutil.rmtree(root, ignore_errors=True)
    project.mkdir(parents=True)
    renders.mkdir()

    (project / f"{NAME}.kicad_pro").write_text("{}\n", encoding="utf-8")
    schematic = project / f"{NAME}.kicad_sch"
    schematic.write_text(EMPTY_SCHEMATIC.format(uuid=uuid.uuid4()), encoding="utf-8")
    index = LibraryIndex(detect_paths(10), project)
    written = write_circuit(schematic, index, SYMBOLS, NETS)
    if not written.get("written"):
        raise SystemExit(f"El esquemático no se escribió: {written.get('errors')}")
    (root / "place_circuit.json").write_text(json.dumps(written, ensure_ascii=False, indent=2), encoding="utf-8")

    with_svg = renders / "svg"
    run([CLI, "sch", "export", "svg", "--exclude-drawing-sheet", "-o", str(with_svg), str(schematic)])
    shutil.copy(with_svg / f"{NAME}.svg", renders / "esquematico.svg")

    spec = root / "placa.json"
    spec.write_text(json.dumps(BOARD), encoding="utf-8")
    python = find_pcbnew_python()
    if not python:
        raise SystemExit("No encuentro el Python de KiCad.")
    empty = project / "vacia.kicad_pcb"
    f8 = project / "f8.kicad_pcb"
    placed = project / f"{NAME}.kicad_pcb"
    run([python, str(HERE / "placa_kicad.py"), str(spec), str(empty), "vacia"])
    run([python, str(HERE / "placa_kicad.py"), str(spec), str(f8), "f8"])
    run([python, str(HERE / "placa_kicad.py"), str(spec), str(placed), "colocada"])

    routed = route_board_files(placed, work_dir=root / "ruteo", fab=FAB, max_passes=40, timeout_s=240)
    if not routed.get("ok"):
        raise SystemExit(f"FreeRouting falló: {routed.get('error')}")
    routed_board = Path(routed.get("candidate") or root / "ruteo" / "board-routed.kicad_pcb")

    drc = root / "drc.json"
    subprocess.run(
        [CLI, "pcb", "drc", "--format", "json", "--severity-error", "-o", str(drc), str(routed_board)],
        capture_output=True, text=True, check=False,
    )
    report = json.loads(drc.read_text(encoding="utf-8"))
    summary = {
        "symbol_libraries": len(index.symbol_libs),
        "footprint_libraries": len(index.footprint_libs),
        "stats": board_stats(routed_board),
        "drc_errors": len(report.get("violations", [])),
        "unconnected": len(report.get("unconnected_items", [])),
    }
    (root / "resumen.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    pcb_svg(empty, renders / "placa-vacia.svg")
    pcb_svg(f8, renders / "placa-f8.svg")
    pcb_svg(placed, renders / "placa-colocada.svg")
    pcb_svg(routed_board, renders / "placa-ruteada.svg")
    run([
        CLI, "pcb", "render", "-w", "1600", "-h", "1000", "--quality", "high", "--side", "top",
        "--rotate", "-40,0,30", "--perspective", "--zoom", "0.9", "-o", str(renders / "placa-3d.png"), str(routed_board),
    ])
    print(json.dumps(summary, indent=2))
    print("Renders en", renders)


if __name__ == "__main__":
    main()
