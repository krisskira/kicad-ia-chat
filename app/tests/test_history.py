import json

from kicad_ia.agent.history import compact_closed_turns, tool_key
from kicad_ia.agent.llm import LlmReply, ScriptedClient, ToolCall
from kicad_ia.agent.loop import Session, run_turn
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.tools.registry import build_registry


def test_compact_closed_turns_strips_heavy_fields():
    messages = [
        {"role": "user", "content": "antes"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "search_parts", "arguments": "{}"}}]},
        {
            "role": "tool",
            "tool_call_id": "1",
            "content": json.dumps(
                {
                    "ok": True,
                    "lib_id": "Device:R",
                    "matches": [{"lib_id": "Device:R"}],
                    "image": "/x.png",
                    "huge": "y" * 5000,
                }
            ),
        },
        {"role": "assistant", "content": "listo"},
    ]
    out = compact_closed_turns(messages)
    body = json.loads(out[2]["content"])
    assert body["compacted"] is True
    assert body["ok"] is True
    assert body["lib_id"] == "Device:R"
    assert "image" not in body
    assert "huge" not in body
    assert out[0]["role"] == "user"


def test_dedup_skips_same_tool_args_in_one_turn():
    gateway = FakeGateway()
    client = ScriptedClient(
        [
            LlmReply(
                "",
                [
                    ToolCall("a", "render_view", {"view": "schematic"}),
                    ToolCall("b", "render_view", {"view": "schematic"}),
                ],
            ),
            LlmReply("Listo."),
        ]
    )
    turn = run_turn(Session("d"), "enséñame", client, build_registry(), gateway)
    assert turn.steps[0]["result"].get("ok") is True
    assert turn.steps[1]["result"].get("deduplicated") is True
    assert tool_key("render_view", {"view": "schematic"}) == tool_key("render_view", {"view": "schematic"})


def test_second_turn_sees_compacted_history():
    gateway = FakeGateway()
    session = Session("c")
    session.messages = [
        {"role": "user", "content": "busca R"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "search_parts", "arguments": '{"kind":"symbol","query":"R"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "t1",
            "content": json.dumps({"ok": True, "matches": [{"lib_id": "Device:R"}], "image": "/old.png", "blob": "x" * 3000}),
        },
        {"role": "assistant", "content": "Encontré Device:R"},
    ]
    client = ScriptedClient([LlmReply("Sin tools.")])
    run_turn(session, "sigue", client, build_registry(), gateway)
    tool_msg = next(m for m in client.seen[0] if m.get("role") == "tool")
    body = json.loads(tool_msg["content"])
    assert body.get("compacted") is True
    assert "blob" not in body
