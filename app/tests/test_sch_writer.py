import pytest

from kicad_ia.kicad.sch_writer import SchematicLocked, lock_file, nets_from_connections, read_symbols, set_footprint, write_circuit
from kicad_ia.kicad.sexpr import children, parse

PAIR = [{"lib_id": "Test:LDO-3.3", "reference": "U1"}, {"lib_id": "Test:LDO-3.3", "reference": "U2"}]
PAIR_NETS = [
    {"name": "VBAT", "pins": [{"reference": "U1", "pin": "VIN"}, {"reference": "U2", "pin": "VIN"}]},
    {"name": "GND", "pins": [{"reference": "U1", "pin": "GND"}, {"reference": "U2", "pin": "GND"}]},
]


def test_writes_symbols_and_net_labels(project, index):
    schematic = project / "demo.kicad_sch"
    result = write_circuit(
        schematic,
        index,
        [
            {"lib_id": "Test:LDO-3.3", "reference": "U1", "footprint": "Test:SOT-23-5"},
            {"lib_id": "Test:LDO-3.3", "reference": "U2"},
        ],
        [
            {"name": "VBAT", "pins": [{"reference": "U1", "pin": "VIN"}, {"reference": "U2", "pin": "VIN"}]},
            {"name": "+3V3", "pins": [{"reference": "U1", "pin": "5"}, {"reference": "U2", "pin": "5"}]},
            {"name": "GND", "pins": [{"reference": "U1", "pin": "GND"}, {"reference": "U2", "pin": "GND"}]},
        ],
    )
    assert result["ok"] is True, result
    assert result["net_stubs"] == 6
    assert result["unconnected_pins"] == {}
    tree = parse(schematic.read_text(encoding="utf-8"))[0]
    labels = sorted(str(node[1]) for node in children(tree, "label"))
    assert labels == ["+3V3", "+3V3", "GND", "GND", "VBAT", "VBAT"]
    embedded = children(children(tree, "lib_symbols")[0], "symbol")
    assert str(embedded[0][1]) == "Test:LDO-3.3"
    assert not children(embedded[0], "extends")
    assert read_symbols(schematic)[0]["reference"] == "U1"
    assert (project / ".kicad-ia-backup").is_dir()


def test_unknown_pin_is_reported(project, index):
    result = write_circuit(
        project / "demo.kicad_sch",
        index,
        [{"lib_id": "Test:LDO-3.3", "reference": "U1"}],
        [{"name": "X", "pins": [{"reference": "U1", "pin": "9"}, {"reference": "U1", "pin": "1"}]}],
    )
    assert result["ok"] is False
    assert "pin 9" in result["errors"][0]


def test_rejects_half_nets_and_unknown_footprints(project, index):
    before = (project / "demo.kicad_sch").read_text(encoding="utf-8")
    result = write_circuit(
        project / "demo.kicad_sch",
        index,
        [{"lib_id": "Test:LDO-3.3", "reference": "U1", "footprint": "Test:Nope"}],
        [{"name": "CS", "pins": [{"reference": "U1", "pin": "1"}]}],
    )
    assert result["written"] is False
    assert any("Test:Nope" in error for error in result["errors"])
    assert any("solo tiene 1 pin" in error for error in result["errors"])
    assert any("GND" in error for error in result["errors"])
    assert (project / "demo.kicad_sch").read_text(encoding="utf-8") == before


def test_replace_clears_previous_design(project, index):
    schematic = project / "demo.kicad_sch"
    write_circuit(schematic, index, PAIR, PAIR_NETS)
    write_circuit(schematic, index, PAIR, PAIR_NETS, replace=True)
    assert sorted(row["reference"] for row in read_symbols(schematic) if not row["reference"].startswith("#")) == ["U1", "U2"]


def test_unknown_symbol_writes_nothing(project, index):
    before = (project / "demo.kicad_sch").read_text(encoding="utf-8")
    result = write_circuit(project / "demo.kicad_sch", index, [{"lib_id": "Test:Nope", "reference": "U1"}], [])
    assert result["ok"] is False
    assert (project / "demo.kicad_sch").read_text(encoding="utf-8") == before


def test_refuses_when_editor_has_it_open(project, index):
    schematic = project / "demo.kicad_sch"
    lock_file(schematic).write_text("", encoding="utf-8")
    with pytest.raises(SchematicLocked):
        write_circuit(schematic, index, PAIR, PAIR_NETS)


def test_set_footprint(project, index):
    schematic = project / "demo.kicad_sch"
    assert write_circuit(schematic, index, PAIR, PAIR_NETS)["ok"] is True
    assert set_footprint(schematic, "U1", "Test:SOT-23-5")["ok"] is True
    assert read_symbols(schematic)[0]["footprint"] == "Test:SOT-23-5"


def test_connections_become_named_nets():
    nets = nets_from_connections(
        [
            {"from_reference": "R1", "from_pin": "2", "to_reference": "R2", "to_pin": "1"},
            {"from_reference": "R2", "from_pin": "1", "to_reference": "C1", "to_pin": "1"},
        ]
    )
    assert len(nets) == 1
    assert len(nets[0]["pins"]) == 3
