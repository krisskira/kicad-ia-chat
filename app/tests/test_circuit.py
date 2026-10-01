from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.geometry import orthogonal_segments, snap_mm


def test_snap_to_schematic_grid():
    assert snap_mm(10) == 10.16
    assert snap_mm(1.27) == 1.27


def test_orthogonal_l_shape():
    segments = orthogonal_segments(0, 0, 2.54, 1.27)
    assert len(segments) == 2
    assert segments[0].x2_mm == 2.54
    assert segments[1].y2_mm == 1.27


def test_place_divider_with_nets():
    gateway = FakeGateway()
    placed = gateway.place_circuit(
        symbols=[
            {"lib_id": "Device:R", "reference": "R1", "value": "10k"},
            {"lib_id": "Device:R", "reference": "R2", "value": "10k"},
        ],
        nets=[
            {"name": "VCC", "pins": [{"reference": "R1", "pin": "1"}]},
            {"name": "MID", "pins": [{"reference": "R1", "pin": "2"}, {"reference": "R2", "pin": "1"}]},
            {"name": "GND", "pins": [{"reference": "R2", "pin": "2"}]},
        ],
        connections=[],
    )
    assert placed["ok"] is True, placed
    assert {item["reference"] for item in placed["placed"]} == {"R1", "R2"}
    assert {label["text"] for label in gateway.labels} == {"VCC", "MID", "GND"}
    synced = gateway.sync_board()
    assert {item["reference"] for item in synced["created"]} == {"R1", "R2"}
    models = gateway.list_models("R1")
    assert "R_0603" in models["models"][0]


def test_net_reports_missing_pin():
    gateway = FakeGateway()
    result = gateway.place_circuit(
        symbols=[{"lib_id": "Device:R", "reference": "R1"}],
        nets=[{"name": "X", "pins": [{"reference": "R1", "pin": "9"}]}],
        connections=[],
    )
    assert result["ok"] is False
    assert "pin 9" in result["errors"][0]


def test_search_requires_known_kind():
    result = FakeGateway().search_parts("symbol", "resisten", 10)
    assert result["ok"] is True
    assert result["matches"][0]["lib_id"] == "Device:R"
