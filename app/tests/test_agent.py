from kicad_ia.agent.dispatch import ChatBook, dispatch
from kicad_ia.agent.llm import LlmReply, ScriptedClient, ToolCall
from kicad_ia.agent.loop import Session, run_turn
from kicad_ia.config import Settings
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry


def test_turn_reads_selection_before_answering():
    gateway = FakeGateway()
    gateway.selected = [{"editor": "pcb", "kind": "FootprintInstance", "reference": "R1", "models": []}]
    client = ScriptedClient(
        [
            LlmReply("", [ToolCall("call-1", "inspect_context", {})]),
            LlmReply("Hay R1 seleccionado en la placa."),
        ]
    )
    turn = run_turn(Session("s"), "qué tengo seleccionado", client, build_registry(), gateway)
    assert turn.steps[0]["tool"] == "inspect_context"
    assert "R1" in turn.reply
    assert "R1" in client.seen[1][-1]["content"]


def test_chat_without_model_still_reads_selection():
    gateway = FakeGateway()
    gateway.selected = [{"editor": "schematic", "kind": "Symbol", "reference": "C3"}]
    book = ChatBook()
    session = book.session(None)
    payload = dispatch("/seleccion", session, Settings(), gateway, build_registry(), None)
    assert "C3" in payload["reply"]
    assert payload["steps"][0]["tool"] == "inspect_context"


def test_system_prompt_follows_ui_language():
    from kicad_ia.agent.loop import system_prompt

    assert "Respondes en inglés" in system_prompt(FakeGateway())
    assert "Respondes en español" in system_prompt(FakeGateway(), lang="es")


def test_unknown_tool_is_reported():
    result = build_registry().call("no_existe", {}, FakeGateway())
    assert result["ok"] is False


def test_turn_stops_when_cancelled_between_tools():
    from kicad_ia.events import TOOL_FINISHED

    gateway = FakeGateway()
    client = ScriptedClient(
        [
            LlmReply(
                "",
                [
                    ToolCall("call-1", "inspect_context", {}),
                    ToolCall("call-2", "inspect_context", {}),
                ],
            ),
            LlmReply("no debería llegar"),
        ]
    )
    stop = {"yes": False}

    def emit(kind, _data):
        if kind == TOOL_FINISHED:
            stop["yes"] = True

    turn = run_turn(
        Session("s"),
        "para",
        client,
        build_registry(),
        gateway,
        emit=emit,
        cancelled=lambda: stop["yes"],
    )
    assert turn.cancelled is True
    assert "Paré" in turn.reply or "Stopped" in turn.reply
    assert len(turn.steps) == 1
    assert len(client.seen) == 1
