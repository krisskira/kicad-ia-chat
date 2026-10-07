import threading
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
        error = _receive_until(ws, "error")["error"]
        assert "previous message" in error or "mensaje anterior" in error
        assert _receive_until(ws, "turn.finished")["reply"] == "ok"


def test_chat_service_cancel_stops_turn():
    from kicad_ia.events import TURN_FINISHED
    from kicad_ia.services.chat import ChatService
    from kicad_ia.tools.registry import build_registry

    settings = Settings(kicad_mode="fake", llm_base_url="http://llm", llm_model="test")
    bus = EventBus()
    seen: list = []
    bus.subscribe(seen.append)
    entered = threading.Event()
    release = threading.Event()

    class Slow:
        def complete(self, *_args):
            entered.set()
            release.wait(2.0)
            return LlmReply(content="llegó tarde", tool_calls=[])

    chat = ChatService(settings, FakeGateway(), build_registry(), Slow(), bus)
    session_id = chat.session_id(None)
    assert chat.submit(session_id, "uno", "es")
    assert entered.wait(2.0)
    assert chat.cancel(session_id) is True
    release.set()
    for _ in range(40):
        if any(event.type == TURN_FINISHED for event in seen):
            break
        time.sleep(0.05)
    finished = [event for event in seen if event.type == TURN_FINISHED][-1]
    assert finished.data.get("cancelled") is True
    assert "Paré" in finished.data["reply"]
    assert chat.busy(session_id) is False


def test_websocket_accepts_chat_cancel():
    settings = Settings(kicad_mode="fake", llm_base_url="http://llm", llm_model="test")
    entered = threading.Event()
    release = threading.Event()

    class Slow:
        def complete(self, *_args):
            entered.set()
            release.wait(2.0)
            return LlmReply(content="llegó tarde", tool_calls=[])

    app = create_app(settings, FakeGateway(), client=Slow())
    with TestClient(app) as http, http.websocket_connect("/ws") as ws:
        ws.receive_json()
        ws.send_json({"type": "chat.send", "text": "uno", "lang": "es"})
        assert _receive_until(ws, "turn.started")
        assert entered.wait(2.0)
        ws.send_json({"type": "chat.cancel"})
        time.sleep(0.05)
        release.set()
        done = _receive_until(ws, "turn.finished")
        assert done.get("cancelled") is True
        assert "Paré" in done["reply"]
