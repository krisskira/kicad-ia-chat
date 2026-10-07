from kicad_ia.agent.llm import LlmReply, ScriptedClient, ToolCall
from kicad_ia.agent.loop import Session, run_turn
from kicad_ia.agent.review import CircuitReviewer, _hard_block
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry


def _ready(name: str) -> Session:
    session = Session(name)
    session.memory.commit({"goal": "esp", "unknowns": []})
    session.memory.accepted["RF_Module:ESP32-S3"] = "RF_Module:ESP32-S3-WROOM-1"
    session.memory.accepted["Device:R"] = "Resistor_SMD:R_0603_1608Metric"
    return session


def test_hard_block_rejects_unknown_pin():
    gateway = FakeGateway()
    problems = _hard_block(
        {
            "symbols": [{"lib_id": "Device:R", "reference": "R1", "value": "10k"}],
            "nets": [{"name": "N", "pins": [{"reference": "R1", "pin": "9"}]}],
        },
        gateway,
    )
    assert problems and "pin 9" in problems[0]


def test_guard_runs_before_reviewer_client():
    """Sin contrato el revisor no se llama."""
    gateway = FakeGateway()
    review_client = ScriptedClient([])
    reviewer = CircuitReviewer(review_client)
    designer = ScriptedClient(
        [
            LlmReply(
                "",
                [
                    ToolCall(
                        "1",
                        "place_circuit",
                        {
                            "symbols": [
                                {
                                    "lib_id": "Device:R",
                                    "reference": "R1",
                                    "value": "10k",
                                    "footprint": "Resistor_SMD:R_0603_1608Metric",
                                }
                            ],
                            "nets": [],
                        },
                    )
                ],
            ),
            LlmReply("Falta contrato."),
        ]
    )
    turn = run_turn(Session("no-intent"), "escribe", designer, build_registry(), gateway, reviewer)
    assert turn.steps[0]["result"]["intent"] == "missing"
    assert review_client.seen == []


def test_hard_rules_work_without_review_model():
    gateway = FakeGateway()
    reviewer = CircuitReviewer(None)
    blocked = reviewer.gate(
        {
            "symbols": [{"lib_id": "Device:R", "reference": "R1", "value": "10k"}],
            "nets": [{"name": "N", "pins": [{"reference": "R1", "pin": "9"}]}],
        },
        gateway,
    )
    assert blocked is not None
    assert blocked["review"] == "rejected"
    assert blocked["problems"]
