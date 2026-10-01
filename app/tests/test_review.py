from kicad_ia.agent.llm import LlmReply, ScriptedClient, ToolCall
from kicad_ia.agent.loop import Session, run_turn
from kicad_ia.agent.review import CircuitReviewer, _verdict
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry

DIVIDER = {
    "symbols": [
        {"lib_id": "Device:R", "reference": "R1"},
        {"lib_id": "Device:R", "reference": "R2"},
    ],
    "nets": [{"name": "MID", "pins": [{"reference": "R1", "pin": "2"}, {"reference": "R2", "pin": "1"}]}],
}


def _place(call_id: str) -> LlmReply:
    return LlmReply("", [ToolCall(call_id, "place_circuit", DIVIDER)])


def test_verdict_reads_tool_call():
    reply = LlmReply("", [ToolCall("r", "verdict", {"approved": False, "problems": ["EN de U2 va a la salida"]})])
    assert _verdict(reply)["problems"] == ["EN de U2 va a la salida"]


def test_rejected_design_is_not_written_until_approved():
    gateway = FakeGateway()
    designer = ScriptedClient([_place("1"), _place("2"), LlmReply("Corregido.")])
    reviewer = CircuitReviewer(
        ScriptedClient(
            [
                LlmReply("", [ToolCall("r1", "verdict", {"approved": False, "problems": ["falta el pull-up"]})]),
                LlmReply("", [ToolCall("r2", "verdict", {"approved": True})]),
            ]
        )
    )
    turn = run_turn(Session("s"), "haz el divisor", designer, build_registry(), gateway, reviewer)
    assert turn.steps[0]["result"]["review"] == "rejected"
    assert turn.steps[0]["result"]["written"] is False
    assert turn.steps[1]["result"]["review"] == "approved"
    assert set(gateway.symbols) == {"R1", "R2"}


def test_review_stops_after_two_rejections():
    gateway = FakeGateway()
    designer = ScriptedClient([_place("1"), _place("2"), _place("3"), LlmReply("Paro.")])
    reviewer_client = ScriptedClient(
        [
            LlmReply("", [ToolCall("r1", "verdict", {"approved": False, "problems": ["mal"]})]),
            LlmReply("", [ToolCall("r2", "verdict", {"approved": False, "problems": ["sigue mal"]})]),
        ]
    )
    reviewer = CircuitReviewer(reviewer_client)
    turn = run_turn(Session("s"), "hazlo", designer, build_registry(), gateway, reviewer)
    assert [step["result"]["review"] for step in turn.steps] == ["rejected", "rejected", "exhausted"]
    assert gateway.symbols == {}
    assert len(reviewer_client.seen) == 2


def test_reviewer_outage_does_not_block_writing():
    class Down:
        def complete(self, messages, tools, system):
            del messages, tools, system
            raise RuntimeError("sin cuota")

    gateway = FakeGateway()
    designer = ScriptedClient([_place("1"), LlmReply("Listo.")])
    turn = run_turn(Session("s"), "hazlo", designer, build_registry(), gateway, CircuitReviewer(Down()))
    assert turn.steps[0]["result"]["review"] == "skipped"
    assert set(gateway.symbols) == {"R1", "R2"}
