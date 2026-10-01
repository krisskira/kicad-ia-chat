def test_reads_project_tables(index):
    assert [row.nickname for row in index.symbol_libs] == ["Test"]
    assert [row.nickname for row in index.footprint_libs] == ["Test"]


def test_search_symbol_by_partial_name(index):
    matches = index.search_symbols("ldo 3.3")
    assert matches[0]["lib_id"] == "Test:LDO-3.3"


def test_derived_symbol_inherits_pins_and_footprint(index):
    part = index.describe_symbol("Test:LDO-3.3")
    assert part["footprint"] == "Test:SOT-23-5"
    pins = {pin["number"]: pin for pin in part["pins"]}
    assert set(pins) == {"1", "2", "5"}
    assert pins["1"]["name"] == "VIN"
    assert pins["1"]["outward"] == "left"
    assert pins["5"]["outward"] == "right"


def test_footprint_model_resolves_against_project(index):
    detail = index.describe_footprint("Test:SOT-23-5")
    assert detail["pad_count"] == 3
    assert detail["mounting"] == "smd"
    assert detail["models"][0]["exists"] is True


def test_unknown_symbol_is_none(index):
    assert index.describe_symbol("Test:Nope") is None
    assert index.search_symbols("zzzz-no-existe") == []
