"""Arma la placa de la demo con pcbnew. Lo ejecuta el Python de KiCad.

  python3 placa_kicad.py <spec.json> <salida.kicad_pcb> f8|colocada

`vacia` es solo el contorno. `f8` deja las huellas fuera del contorno, como
quedan tras «Actualizar PCB desde el esquemático». `colocada` las pone en las
posiciones de la propuesta.
"""

import json
import sys
from pathlib import Path

import pcbnew

FOOTPRINTS = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")


def mm(value):
    return pcbnew.FromMM(value)


def point(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def outline(board, x, y, width, height):
    corners = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        line = pcbnew.PCB_SHAPE(board)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(point(*start))
        line.SetEnd(point(*end))
        line.SetLayer(pcbnew.Edge_Cuts)
        line.SetWidth(mm(0.1))
        board.Add(line)


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    target = sys.argv[2]
    mode = sys.argv[3]
    board = pcbnew.BOARD()
    nets = {}
    for name in spec["nets"]:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        nets[name] = net

    edge = spec["board"]
    outline(board, edge["x"], edge["y"], edge["width"], edge["height"])

    parts = [] if mode == "vacia" else spec["parts"]
    for index, part in enumerate(parts):
        library, _, name = part["footprint"].partition(":")
        footprint = pcbnew.FootprintLoad(str(FOOTPRINTS / f"{library}.pretty"), name)
        footprint.SetReference(part["reference"])
        footprint.SetValue(part["value"])
        footprint.SetFPIDAsString(part["footprint"])
        for pad in footprint.Pads():
            net = part["pads"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        if mode == "f8":
            x = edge["x"] + edge["width"] + 8 + (index % 3) * 9
            y = edge["y"] + (index // 3) * 9
            footprint.SetPosition(point(x, y))
        else:
            x, y, angle = part["at"]
            footprint.SetPosition(point(edge["x"] + x, edge["y"] + y))
            footprint.SetOrientationDegrees(angle)
        board.Add(footprint)

    pcbnew.SaveBoard(target, board)


main()
