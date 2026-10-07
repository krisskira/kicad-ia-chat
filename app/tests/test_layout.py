from kicad_ia.kicad.layout import Box, auto_groups, group_layout, normalize_groups, plan_stages, shelf_pack
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
    assert groups["Alimentación (U1)"] == ["U1", "C1", "C2"]
    assert set(groups["Microcontrolador (U2)"]) == {"U2", "R1", "R2", "D1"}


def test_stage_plan_eligible_with_two_named_groups():
    plan = plan_stages(COMPONENTS, NETS)
    assert plan.eligible is True
    assert plan.draw_frames is True
    assert plan.ambiguous == []
    assert len([g for g in plan.groups if g["name"] != "Otros"]) >= 2


def test_single_group_is_not_framed():
    comps = [{"reference": "U1", "value": "AP2112K"}, {"reference": "C1", "value": "1u"}]
    nets = [
        {"name": "VBAT", "nodes": [_node("U1", "1", "power_in"), _node("C1", "1")]},
        {"name": "GND", "nodes": [_node("U1", "2", "power_in"), _node("C1", "2")]},
    ]
    plan = plan_stages(comps, nets)
    assert plan.draw_frames is False
    assert plan.eligible is False


def test_shared_bus_marks_ambiguous():
    comps = [
        {"reference": "U1", "value": "MCU"},
        {"reference": "U2", "value": "Sensor"},
        {"reference": "R1", "value": "4k7"},
    ]
    nets = [
        {"name": "I2C_SDA", "nodes": [_node("U1", "1"), _node("U2", "1"), _node("R1", "1")]},
        {"name": "+3V3", "nodes": [_node("U1", "2", "power_in"), _node("U2", "2", "power_in"), _node("R1", "2")]},
    ]
    plan = plan_stages(comps, nets)
    assert "R1" in plan.ambiguous
    assert plan.draw_frames is False


def test_connectors_merge_when_lonely():
    comps = [
        {"reference": "J1", "value": "USB"},
        {"reference": "J2", "value": "UART"},
        {"reference": "U1", "value": "ESP32"},
    ]
    nets = [
        {"name": "USB_DP", "nodes": [_node("J1", "1"), _node("U1", "10")]},
        {"name": "TX", "nodes": [_node("J2", "1"), _node("U1", "11")]},
    ]
    plan = plan_stages(comps, nets)
    # J1/J2 tienen señal con U1 → no son «lonely»; cada uno o el MCU los absorbe.
    names = {g["name"] for g in plan.groups}
    assert "Microcontrolador (U1)" in names or any("U1" in g["name"] for g in plan.groups)


def test_lonely_connectors_form_group():
    comps = [
        {"reference": "J1", "value": "USB"},
        {"reference": "J2", "value": "HDR"},
        {"reference": "U1", "value": "ESP32"},
        {"reference": "R1", "value": "10k"},
    ]
    nets = [
        {"name": "EN", "nodes": [_node("U1", "3"), _node("R1", "1")]},
        {"name": "+3V3", "nodes": [_node("U1", "2", "power_in"), _node("R1", "2")]},
        # Conectores sin redes de señal hacia el MCU → lonely.
    ]
    plan = plan_stages(comps, nets)
    assert any(g["name"] == "Conectores" and set(g["references"]) == {"J1", "J2"} for g in plan.groups)


def test_explicit_groups_override_auto():
    plan = plan_stages(
        COMPONENTS,
        NETS,
        groups=[{"name": "Power", "references": ["U1", "C1", "C2"]}, {"name": "Logic", "references": ["U2", "R1", "R2", "D1"]}],
    )
    assert plan.auto is False
    assert plan.draw_frames is True
    assert [g["name"] for g in plan.groups] == ["Power", "Logic"]


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
    result = write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True, groups=groups, draw_frames=True)
    assert result["ok"] is True, result
    tree = parse(schematic.read_text(encoding="utf-8"))[0]
    assert len(children(tree, "rectangle")) == 2
    assert sorted(str(node[1]) for node in children(tree, "text")) == ["Regulador A", "Regulador B"]
    again = write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True, groups=groups, draw_frames=True)
    assert again["ok"] is True
    assert len(children(parse(schematic.read_text(encoding="utf-8"))[0], "rectangle")) == 2


def test_grouped_schematic_can_skip_frames(project, index):
    schematic = project / "demo.kicad_sch"
    groups = [{"name": "Circuito", "references": ["U1", "U2"]}]
    result = write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True, groups=groups, draw_frames=False)
    assert result["ok"] is True, result
    tree = parse(schematic.read_text(encoding="utf-8"))[0]
    assert children(tree, "rectangle") == []


def test_fake_organize_preview_returns_stage_fields():
    from kicad_ia.kicad.fake import FakeGateway

    gateway = FakeGateway()
    gateway.place_circuit(
        [
            {"lib_id": "Device:R", "reference": "R1", "value": "10k", "footprint": "Resistor_SMD:R_0603_1608Metric"},
            {"lib_id": "Device:C", "reference": "C1", "value": "100n", "footprint": "Capacitor_SMD:C_0603_1608Metric"},
        ],
        [{"name": "N1", "pins": [{"reference": "R1", "pin": "1"}, {"reference": "C1", "pin": "1"}]}],
        [],
    )
    # Aceptar huellas vía memoria no hace falta: place_circuit en fake no usa guard.
    preview = gateway.organize_layout("schematic", None, apply=False)
    assert preview["ok"] is True
    assert "groups" in preview
    assert "eligible" in preview
    assert "draw_frames" in preview
    assert preview["schematic"]["applied"] is False
