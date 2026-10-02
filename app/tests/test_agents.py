from kicad_ia.agent.components import select_component
from kicad_ia.agent.intent import DesignMemory, guard_place
from kicad_ia.kicad.board_area import area_from_boxes, board_area_report
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry


def test_missing_part_is_not_invented():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "XYZ123"}, memory)
    assert result["decision"] == "request_user"
    assert result["candidates"] == []
    assert memory.accepted == set()


def test_exact_library_part_can_be_selected():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "Device:R"}, memory)
    assert result["decision"] == "selected"
    assert result["autonomy"] == "automatic"
    assert "Device:R" in memory.accepted


def test_substitute_is_not_chosen_alone():
    memory = DesignMemory()
    result = select_component(
        FakeGateway(),
        {"requested_part": "XYZ123", "function": "Regulador", "hard": {"voltage": "5V"}},
        memory,
    )
    assert result["decision"] == "decision_required"
    assert memory.accepted == set()
    assert all(row["checks"]["voltage"] == "UNKNOWN" for row in result["candidates"])


def test_confirmed_substitution_records_change_set():
    memory = DesignMemory()
    result = select_component(
        FakeGateway(),
        {"requested_part": "XYZ123", "function": "Regulador", "allow_substitution": True},
        memory,
    )
    assert result["decision"] == "selected"
    assert result["change_set"]["replacement"] == "Regulator_Linear:AP2112K-3.3"
    assert result["change_set"]["classification"] == "UNVERIFIED"
    assert memory.substitutions["XYZ123"] == "Regulator_Linear:AP2112K-3.3"


def test_pin_mismatch_is_rejected():
    memory = DesignMemory()
    result = select_component(
        FakeGateway(),
        {"requested_part": "Device:R", "required_pins": ["EN"]},
        memory,
    )
    assert result["decision"] == "request_user"
    assert memory.accepted == set()


def test_contract_keeps_required_component():
    memory = DesignMemory()
    assert memory.commit({"goal": "placa", "required_components": ["ESP32"]})["ok"]
    blocked = memory.commit({"goal": "placa", "required_components": []})
    assert blocked["intent"] == "CONTRADICTS_REQUIREMENT"
    assert memory.contract.version == 1
    updated = memory.commit({"goal": "placa", "required_components": [], "confirm_removed": ["ESP32"]})
    assert updated["contract"]["version"] == 2


def test_place_blocks_missing_intent_and_missing_part():
    gateway = FakeGateway()
    registry = build_registry()
    blocked = registry.call(
        "place_circuit",
        {"symbols": [{"lib_id": "Device:R", "reference": "R1"}], "nets": []},
        gateway,
    )
    assert blocked["intent"] == "missing"
    memory = gateway.design_memory
    memory.commit({"goal": "leds", "required_components": ["ESP32"]})
    memory.accepted.add("Device:R")
    contradicted = guard_place(memory, [{"lib_id": "Device:R", "reference": "R1"}])
    assert contradicted["intent"] == "CONTRADICTS_REQUIREMENT"


def test_board_area_uses_footprints_or_asks_for_a_measure():
    proposal = area_from_boxes([(0, 0, 10, 6), (20, 0, 8, 6)])
    assert proposal["width_mm"] == 38.0
    assert proposal["height_mm"] == 16.0
    missing = board_area_report(None, [])
    assert missing["proposal"] is None
    assert "a ojo" in missing["must_tell_user"]
    defined = board_area_report((0, 0, 40, 30), [])
    assert defined["status"] == "defined"
    gateway = FakeGateway()
    gateway.sync_board()
    assert gateway.sync_board()["board_area"]["status"] == "missing"
