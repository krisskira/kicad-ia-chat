from kicad_ia.kicad.layout import Box, auto_groups, group_layout, normalize_groups, shelf_pack
from kicad_ia.kicad.sch_writer import write_circuit
from kicad_ia.kicad.sexpr import children, parse

PAIR = [{"lib_id": "Test:LDO-3.3", "reference": "U1"}, {"lib_id": "Test:LDO-3.3", "reference": "U2"}]
PAIR_NETS = [
    {"name": "VBAT", "pins": [{"reference": "U1", "pin": "VIN"}, {"reference": "U2", "pin": "VIN"}]},
    {"name": "GND", "pins": [{"reference": "U1", "pin": "GND"}, {"reference": "U2", "pin": "GND"}]},
]


def _node(ref, pin, pintype=""):
    return {"ref": ref, "pin": pin, "pintype": pintype}


COMPONENTS = [
    {"reference": "U1", "value": "AP2112K"},
    {"reference": "U2", "value": "ESP32"},
    {"reference": "C1", "value": "1u"},
    {"reference": "C2", "value": "100n"},
    {"reference": "R1", "value": "10k"},
    {"reference": "R2", "value": "330"},
    {"reference": "D1", "value": "LED"},
]
NETS = [
    {"name": "VBAT", "nodes": [_node("U1", "1", "power_in"), _node("C1", "1")]},
    {"name": "+3V3", "nodes": [_node("U1", "5", "power_out"), _node("U2", "2", "power_in"), _node("C2", "1"), _node("R1", "1")]},
    {"name": "GND", "nodes": [_node("U1", "2", "power_in"), _node("U2", "1", "power_in"), _node("C1", "2"), _node("C2", "2")]},
    {"name": "EN", "nodes": [_node("U2", "3", "input"), _node("R1", "2")]},
    {"name": "LED_K", "nodes": [_node("U2", "10", "bidirectional"), _node("R2", "1")]},
    {"name": "LED_A", "nodes": [_node("R2", "2"), _node("D1", "1")]},
]


def test_passives_join_the_chip_they_serve():
    groups = {group["name"]: group["references"] for group in auto_groups(COMPONENTS, NETS)}
    assert groups["U1 AP2112K"] == ["U1", "C1", "C2"]
    assert set(groups["U2 ESP32"]) == {"U2", "R1", "R2", "D1"}


def test_normalize_drops_unknown_and_keeps_leftovers():
    clean, unknown = normalize_groups([{"name": "Power", "references": ["U1", "X9", "U1"]}], ["U1", "R1"])
    assert clean == [{"name": "Power", "references": ["U1"]}, {"name": "Otros", "references": ["R1"]}]
    assert unknown == ["X9"]


def test_shelf_pack_wraps_rows_without_overlap():
    boxes = [Box(str(index), 30, 10) for index in range(4)]
    width, height = shelf_pack(boxes, 70, 5)
    assert width <= 70
    assert height == 25
    assert boxes[2].y == 15


def test_group_layout_keeps_groups_apart():
    sizes = {ref: (10.0, 8.0) for ref in ("U1", "C1", "U2", "R1")}
    groups = [{"name": "A", "references": ["U1", "C1"]}, {"name": "B", "references": ["U2", "R1"]}]
    centers, blocks, _ = group_layout(sizes, groups, 200, item_gap=2, group_gap=10, padding=2)
    first, second = blocks
    assert first.x + first.width + 10 <= second.x + 0.001
    assert first.x <= centers["U1"][0] <= first.x + first.width
    assert second.x <= centers["R1"][0] <= second.x + second.width


def test_grouped_schematic_draws_frames(project, index):
    schematic = project / "demo.kicad_sch"
    groups = [{"name": "Regulador A", "references": ["U1"]}, {"name": "Regulador B", "references": ["U2"]}]
    result = write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True, groups=groups)
    assert result["ok"] is True, result
    tree = parse(schematic.read_text(encoding="utf-8"))[0]
    assert len(children(tree, "rectangle")) == 2
    assert sorted(str(node[1]) for node in children(tree, "text")) == ["Regulador A", "Regulador B"]
    again = write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True, groups=groups)
    assert again["ok"] is True
    assert len(children(parse(schematic.read_text(encoding="utf-8"))[0], "rectangle")) == 2
