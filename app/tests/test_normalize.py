from types import SimpleNamespace

from kicad_ia.kicad.normalize import normalize_item


def test_normalize_footprint_selection():
    pad = SimpleNamespace(net=SimpleNamespace(name="VCC"))
    model = SimpleNamespace(filename="R_0603.step")
    definition = SimpleNamespace(
        id=SimpleNamespace(library_nickname="Resistor_SMD", entry_name="R_0603_1608Metric"),
        models=[model],
        pads=[pad],
    )
    field = SimpleNamespace(text=SimpleNamespace(value="R1"))
    item = SimpleNamespace(
        reference_field=field,
        value_field=SimpleNamespace(text=SimpleNamespace(value="10k")),
        definition=definition,
        id="abc",
        footprint_field=None,
    )
    data = normalize_item(item, "pcb")
    assert data["reference"] == "R1"
    assert data["value"] == "10k"
    assert data["lib_id"] == "Resistor_SMD:R_0603_1608Metric"
    assert data["models"] == ["R_0603.step"]
    assert data["nets"] == ["VCC"]
    assert data["editor"] == "pcb"
