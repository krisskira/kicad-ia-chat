from kicad_ia.agent.components import select_component
from kicad_ia.agent.intent import DesignMemory, guard_place
from kicad_ia.agent.llm import TokenMeter, parse_usage
from kicad_ia.kicad.board_area import area_from_boxes, board_area_report
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry

R_0603 = "Resistor_SMD:R_0603_1608Metric"


class NoDefaultFootprint(FakeGateway):
    """Como Device:R en KiCad real: sin huella, con filtros ki_fp_filters."""

    def describe_part(self, lib_id: str) -> dict:
        result = super().describe_part(lib_id)
        if result.get("ok") and lib_id == "Device:R":
            part = dict(result["part"], footprint="", footprint_filters=["R_*"])
            return {**result, "part": part}
        return result


def test_missing_part_is_not_invented():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "XYZ123"}, memory)
    assert result["decision"] == "request_user"
    assert result["candidates"] == []
    assert memory.accepted == {}


def test_exact_library_part_is_selected_with_its_footprint():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "Device:R"}, memory)
    assert result["decision"] == "selected"
    assert result["autonomy"] == "automatic"
    assert result["footprint"] == R_0603
    assert result["candidate"]["checks"]["footprint"] == "PASS"
    assert memory.accepted["Device:R"] == R_0603


def test_symbol_without_footprint_is_not_accepted():
    memory = DesignMemory()
    gateway = NoDefaultFootprint()
    result = select_component(gateway, {"requested_part": "Device:R"}, memory)
    assert result["decision"] == "footprint_required"
    assert R_0603 in result["footprint_candidates"]
    assert memory.accepted == {}
    chosen = select_component(gateway, {"requested_part": "Device:R", "footprint": R_0603}, memory)
    assert chosen["decision"] == "selected"
    assert memory.accepted["Device:R"] == R_0603


def test_footprint_outside_libraries_is_rejected():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "Device:R", "footprint": "Inventada:R_9999"}, memory)
    assert result["decision"] == "request_user"
    assert result["candidate"]["checks"]["footprint"] == "FAIL"
    assert memory.accepted == {}


def test_footprint_with_fewer_pads_than_pins_is_rejected():
    memory = DesignMemory()
    result = select_component(
        FakeGateway(),
        {"requested_part": "Regulator_Linear:AP2112K-3.3", "footprint": R_0603},
        memory,
    )
    assert result["candidate"]["checks"]["footprint"] == "FAIL"
    assert "pads" in result["candidate"]["footprint_detail"]["error"]


def test_power_symbol_needs_no_footprint():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "power:GND"}, memory)
    assert result["decision"] == "selected"
    assert result["candidate"]["checks"]["footprint"] == "NOT_REQUIRED"
    assert memory.accepted["power:GND"] == ""


def test_substitute_is_not_chosen_alone():
    memory = DesignMemory()
    result = select_component(
        FakeGateway(),
        {"requested_part": "XYZ123", "function": "Regulador", "hard": {"voltage": "5V"}},
        memory,
    )
    assert result["decision"] == "decision_required"
    assert memory.accepted == {}
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
    assert result["change_set"]["footprint"] == "Package_TO_SOT_SMD:SOT-23-5"
    assert result["change_set"]["classification"] == "UNVERIFIED"
    assert memory.substitutions["XYZ123"] == "Regulator_Linear:AP2112K-3.3"


def test_pin_mismatch_is_rejected():
    memory = DesignMemory()
    result = select_component(FakeGateway(), {"requested_part": "Device:R", "required_pins": ["EN"]}, memory)
    assert result["decision"] == "request_user"
    assert memory.accepted == {}


def test_contract_keeps_required_component():
    memory = DesignMemory()
    assert memory.commit({"goal": "placa", "required_components": ["ESP32"]})["ok"]
    blocked = memory.commit({"goal": "placa", "required_components": []})
    assert blocked["intent"] == "CONTRADICTS_REQUIREMENT"
    assert memory.contract.version == 1
    updated = memory.commit({"goal": "placa", "required_components": [], "confirm_removed": ["ESP32"]})
    assert updated["contract"]["version"] == 2
    assert [row.version for row in memory.history] == [1]


def test_place_blocks_missing_intent_and_missing_part():
    gateway = FakeGateway()
    registry = build_registry()
    blocked = registry.call("place_circuit", {"symbols": [{"lib_id": "Device:R", "reference": "R1"}], "nets": []}, gateway)
    assert blocked["intent"] == "missing"
    memory = gateway.design_memory
    memory.commit({"goal": "leds", "required_components": ["ESP32"]})
    memory.accepted["Device:R"] = R_0603
    contradicted = guard_place(memory, [{"lib_id": "Device:R", "reference": "R1"}])
    assert contradicted["intent"] == "CONTRADICTS_REQUIREMENT"


def test_place_fills_and_checks_the_verified_footprint():
    memory = DesignMemory()
    memory.commit({"goal": "divisor"})
    memory.accepted["Device:R"] = R_0603
    symbols = [{"lib_id": "Device:R", "reference": "R1"}]
    assert guard_place(memory, symbols) is None
    assert symbols[0]["footprint"] == R_0603
    other = guard_place(memory, [{"lib_id": "Device:R", "reference": "R2", "footprint": "Resistor_SMD:R_0805_2012Metric"}])
    assert other["intent"] == "footprint_unverified"


def test_token_meter_sums_provider_usage():
    meter = TokenMeter()
    meter.add({"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150})
    meter.add(None)
    snap = meter.snapshot()
    assert snap == {"prompt": 120, "completion": 30, "total": 150, "calls": 2, "reported": True, "estimated": False}


def test_zero_usage_does_not_count_as_reported_and_gemini_metadata_does():
    assert parse_usage({"usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})[2] is False
    assert parse_usage({"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4}}) == (10, 4, True)
    meter = TokenMeter()
    meter.add_estimate(80, 20)
    snap = meter.snapshot()
    assert snap["estimated"] is True
    assert snap["total"] == 100


def test_board_area_uses_footprints_or_asks_for_a_measure():
    proposal = area_from_boxes([(0, 0, 10, 6), (20, 0, 8, 6)])
    assert proposal["width_mm"] == 38.0
    assert proposal["height_mm"] == 16.0
    missing = board_area_report(None, [])
    assert missing["proposal"] is None
    assert "a ojo" in missing["must_tell_user"]
    assert board_area_report((0, 0, 40, 30), [])["status"] == "defined"
    gateway = FakeGateway()
    assert gateway.sync_board()["board_area"]["status"] == "missing"
