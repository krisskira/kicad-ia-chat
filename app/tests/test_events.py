import time

from fastapi.testclient import TestClient

from kicad_ia.agent.llm import LlmReply, ScriptedClient, ToolCall
from kicad_ia.config import Settings
from kicad_ia.events import SELECTION, STATUS, Event, EventBus
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.serialized import SerializedGateway
from kicad_ia.server.app import create_app
from kicad_ia.services.watcher import KicadWatcher


def test_bus_survives_a_broken_subscriber():
    bus = EventBus()
    seen = []
    bus.subscribe(lambda event: 1 / 0)
    unsubscribe = bus.subscribe(seen.append)
    bus.publish(Event("x"))
    unsubscribe()
    bus.publish(Event("y"))
    assert [event.type for event in seen] == ["x"]


def test_watcher_publishes_only_changes():
    bus = EventBus()
    seen = []
    bus.subscribe(seen.append)
    gateway = FakeGateway()
    watcher = KicadWatcher(Settings(kicad_mode="fake"), SerializedGateway(gateway), bus)
    watcher.poll_once()
    watcher.poll_once()
    assert [event.type for event in seen] == [STATUS, SELECTION]
    gateway.selected = [{"reference": "R1"}]
    watcher.poll_once()
    assert seen[-1].type == SELECTION
    assert seen[-1].data["items"] == [{"reference": "R1"}]


def test_watcher_swaps_in_kicad_when_it_appears():
    fallback = FakeGateway()
    fallback.fallback_reason = "no responde"
    shared = SerializedGateway(fallback)
    fresh = FakeGateway()
    watcher = KicadWatcher(Settings(), shared, EventBus(), connect=lambda: fresh)
    watcher.poll_once()
    assert shared.inner is fresh


def _receive_until(ws, kind, limit=40):
    for _ in range(limit):
        message = ws.receive_json()
        if message["type"] == kind:
            return message
    raise AssertionError(f"No llegó {kind}")


def test_websocket_streams_a_turn():
    client = ScriptedClient(
        [
            LlmReply(content="", tool_calls=[ToolCall(id="1", name="render_view", arguments={"view": "schematic"})]),
            LlmReply(content="Aquí está.", tool_calls=[]),
        ]
    )
    settings = Settings(kicad_mode="fake", llm_base_url="http://llm", llm_model="test")
    app = create_app(settings, FakeGateway(), client=client)
    with TestClient(app) as http, http.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["status"]["capabilities"]["backend"] == "fake"
        assert "render_view" in hello["tools"]
        ws.send_json({"type": "ping"})
        assert _receive_until(ws, "pong")
        ws.send_json({"type": "chat.send", "text": "enséñame el esquemático"})
        assert _receive_until(ws, "turn.started")["text"] == "enséñame el esquemático"
        started = _receive_until(ws, "tool.started")
        assert started["tool"] == "render_view"
        finished = _receive_until(ws, "tool.finished")
        image = finished["result"]["image"]
        assert image.startswith("/renders/")
        done = _receive_until(ws, "turn.finished")
        assert done["reply"] == "Aquí está."
        assert http.get(image).status_code == 200

    with TestClient(app) as http, http.websocket_connect(f"/ws?session={hello['session_id']}") as ws:
        again = ws.receive_json()
        roles = [row["role"] for row in again["history"]]
        assert roles == ["user", "image", "assistant"]


def test_websocket_rejects_a_second_message_while_busy():
    settings = Settings(kicad_mode="fake", llm_base_url="http://llm", llm_model="test")

    class Slow:
        def complete(self, *_args):
            time.sleep(0.3)
            return LlmReply(content="ok", tool_calls=[])

    app = create_app(settings, FakeGateway(), client=Slow())
    with TestClient(app) as http, http.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat.send", "text": "uno"})
        ws.send_json({"type": "chat.send", "text": "dos"})
        assert "anterior" in _receive_until(ws, "error")["error"]
        assert _receive_until(ws, "turn.finished")["reply"] == "ok"
