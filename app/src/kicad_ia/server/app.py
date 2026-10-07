"""Servidor local del chat. KiCad lanza este proceso; también se arranca desde el terminal.

El navegador abre un WebSocket en /ws. El vigilante publica estado y selección
cuando cambian y el servicio de chat publica cada paso del turno; el hub los reparte.

Endpoints útiles:
- GET/PUT /api/settings — Ajustes LLM / Java / autoruteo
- POST /api/settings/probe-java — detección de Java
- GET /api/tools — nombres de herramientas (respeta autoruteo off)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from kicad_ia.agent.llm import OpenAiCompatibleClient
from kicad_ia.config import Settings
from kicad_ia.events import EventBus
from kicad_ia.i18n import normalize_lang, tr
from kicad_ia.kicad.freerouting import probe_java
from kicad_ia.kicad.gateway import Gateway
from kicad_ia.kicad.render import renders_dir
from kicad_ia.kicad.serialized import SerializedGateway
from kicad_ia.kicad.session import open_gateway
from kicad_ia.server.hub import Hub
from kicad_ia.services.chat import ChatService
from kicad_ia.services.watcher import KicadWatcher, selection_payload, status_payload
from kicad_ia.tools.registry import ToolRegistry, build_registry
from kicad_ia.user_prefs import load_prefs, public_prefs, save_prefs

STATIC = Path(__file__).resolve().parent / "static"
MAX_MESSAGE = 8000
log = logging.getLogger(__name__)


class ChatIn(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE)
    session_id: str | None = None
    lang: str | None = None


class SettingsIn(BaseModel):
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    keep_api_key: bool = True
    llm_model: str | None = None
    llm_review_model: str | None = None
    java_bin: str | None = None
    autoroute_enabled: bool | None = None
    fab: dict | None = None


class JavaProbeIn(BaseModel):
    java_bin: str = ""


def _excluded_tools(settings: Settings) -> set[str]:
    return {"autoroute_board"} if not settings.autoroute_enabled else set()


def _refresh_llm(settings: Settings, chat: ChatService) -> None:
    client = OpenAiCompatibleClient(settings, role="main") if settings.llm_ready else None
    chat.apply_runtime(settings, client)


def _connector(settings: Settings):
    if settings.kicad_mode == "fake":
        return None

    def connect():
        from kicad_ia.kicad.kipy_gateway import KipyGateway

        return KipyGateway(settings)

    return connect


def create_app(
    settings: Settings | None = None,
    gateway: Gateway | None = None,
    registry: ToolRegistry | None = None,
    client=None,
    watch: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    connector = _connector(settings) if gateway is None else None
    shared = SerializedGateway(gateway or open_gateway(settings))
    registry = registry or build_registry()
    if client is None and settings.llm_ready:
        client = OpenAiCompatibleClient(settings, role="main")
    bus = EventBus()
    hub = Hub(bus)
    watcher = KicadWatcher(settings, shared, bus, settings.watch_interval, connector)
    chat = ChatService(settings, shared, registry, client, bus, on_turn_end=lambda: watcher.poke())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.bind(asyncio.get_running_loop())
        if watch:
            watcher.start()
        try:
            yield
        finally:
            watcher.stop()
            chat.shutdown()
            hub.close()

    app = FastAPI(title="KiCad IA", lifespan=lifespan)
    app.state.settings = settings
    app.state.gateway = shared
    app.state.registry = registry
    app.state.bus = bus
    app.state.hub = hub
    app.state.watcher = watcher
    app.state.chat = chat

    @app.get("/api/status")
    def status() -> dict:
        return status_payload(settings, shared)

    @app.get("/api/selection")
    def selection() -> dict:
        return selection_payload(shared)

    @app.get("/api/tools")
    def tools() -> dict:
        return {"tools": registry.names(exclude=_excluded_tools(settings))}

    @app.get("/api/settings")
    def get_settings() -> dict:
        prefs = load_prefs()
        # Refleja lo efectivo (prefs + .env) en la UI
        view = public_prefs(
            {
                **prefs,
                "llm_base_url": settings.llm_base_url or prefs.get("llm_base_url") or "",
                "llm_api_key": settings.llm_api_key or prefs.get("llm_api_key") or "",
                "llm_model": settings.llm_model or prefs.get("llm_model") or "",
                "llm_review_model": settings.llm_review_model
                if settings.llm_review_model is not None
                else prefs.get("llm_review_model") or "",
                "java_bin": settings.java_bin or prefs.get("java_bin") or "",
                "autoroute_enabled": settings.autoroute_enabled,
                "fab": settings.fab_summary(),
            }
        )
        view["java_probe"] = probe_java(settings.java_bin)
        view["llm_ready"] = settings.llm_ready
        return view

    @app.put("/api/settings")
    def put_settings(body: SettingsIn) -> dict:
        current = load_prefs()
        payload = {
            "llm_base_url": body.llm_base_url if body.llm_base_url is not None else current.get("llm_base_url", ""),
            "llm_model": body.llm_model if body.llm_model is not None else current.get("llm_model", ""),
            "llm_review_model": body.llm_review_model
            if body.llm_review_model is not None
            else current.get("llm_review_model", ""),
            "java_bin": body.java_bin if body.java_bin is not None else current.get("java_bin", ""),
            "autoroute_enabled": body.autoroute_enabled
            if body.autoroute_enabled is not None
            else bool(current.get("autoroute_enabled")),
            "fab": body.fab if body.fab is not None else current.get("fab"),
        }
        if body.llm_api_key:
            payload["llm_api_key"] = body.llm_api_key
        elif body.keep_api_key:
            payload["llm_api_key"] = current.get("llm_api_key") or settings.llm_api_key or ""
        else:
            payload["llm_api_key"] = ""
            payload["_clear_api_key"] = True
        try:
            saved = save_prefs(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        settings.apply_prefs({**saved, "_clear_api_key": bool(payload.get("_clear_api_key"))})
        _refresh_llm(settings, chat)
        underlying = getattr(shared, "inner", None)
        if underlying is not None and hasattr(underlying, "_settings"):
            underlying._settings = settings
        watcher.poke(force=True)
        return get_settings()

    @app.post("/api/settings/probe-java")
    def probe_java_endpoint(body: JavaProbeIn) -> dict:
        return probe_java(body.java_bin.strip())

    @app.post("/api/chat")
    def chat_once(body: ChatIn) -> dict:
        return chat.run_sync(body.session_id, body.message, lang=normalize_lang(body.lang))

    @app.websocket("/ws")
    async def socket(ws: WebSocket) -> None:
        await ws.accept()
        session_id = chat.session_id(ws.query_params.get("session"))
        client = hub.connect(session_id)
        client.lang = normalize_lang(ws.query_params.get("lang"))
        try:
            await ws.send_json(await _hello(session_id))
            sender = asyncio.create_task(_pump(ws, client.queue))
            try:
                while True:
                    message = await ws.receive_json()
                    reply = await _handle(message, client)
                    if reply is not None:
                        await ws.send_json(reply)
            finally:
                sender.cancel()
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("WebSocket cerrado por error")
        finally:
            hub.disconnect(client)

    async def _hello(session_id: str) -> dict:
        snapshot = hub.snapshot
        state = snapshot.get("status") or await asyncio.to_thread(status_payload, settings, shared)
        picked = snapshot.get("selection") or await asyncio.to_thread(selection_payload, shared)
        return {
            "type": "hello",
            "session_id": session_id,
            "status": state,
            "selection": picked,
            "tools": registry.names(exclude=_excluded_tools(settings)),
            "busy": chat.busy(session_id),
            "history": chat.history(session_id),
            "sessions": chat.summaries(),
        }

    async def _handle(message: dict, client) -> dict | None:
        kind = message.get("type") if isinstance(message, dict) else None
        if kind == "ping":
            return {"type": "pong"}
        if kind == "ui.lang":
            client.lang = normalize_lang(message.get("lang"))
            return None
        if kind == "status.refresh":
            watcher.poke(force=True)
            return None
        if kind == "session.reset" or kind == "session.bind":
            if kind == "session.bind" and chat.busy(client.session_id):
                return {"type": "error", "error": tr(client.lang, "busy")}
            fresh = chat.session_id(None)
            hub.move(client, fresh)
            opened = await _hello(fresh)
            if kind == "session.bind":
                opened["type"] = "session.opened"
            return opened
        if kind == "session.sync":
            chat.session_id(client.session_id)
            listing = await _hello(client.session_id)
            listing["type"] = "sessions"
            return listing
        if kind == "session.preview" or kind == "session.open":
            wanted = str(message.get("session_id") or "")
            preview = chat.preview(wanted, client.lang)
            if preview is None:
                return {"type": "error", "error": tr(client.lang, "unknown_session")}
            return {"type": "session.preview", **preview}
        if kind == "session.delete":
            if chat.busy(client.session_id):
                return {"type": "error", "error": tr(client.lang, "busy")}
            wanted = str(message.get("session_id") or "")
            chat.forget(wanted)
            if client.session_id == wanted:
                fresh = chat.session_id(None)
                hub.move(client, fresh)
                return await _hello(fresh)
            listing = await _hello(client.session_id)
            listing["type"] = "sessions"
            return listing
        if kind == "chat.send":
            text = str(message.get("text") or "").strip()[:MAX_MESSAGE]
            if message.get("lang"):
                client.lang = normalize_lang(message.get("lang"))
            if not text:
                return {"type": "error", "error": tr(client.lang, "empty_message")}
            if chat.submit(client.session_id, text, client.lang) is None:
                return {"type": "error", "error": tr(client.lang, "busy")}
            return None
        if kind == "chat.cancel":
            if not chat.cancel(client.session_id):
                return {"type": "error", "error": tr(client.lang, "nothing_to_cancel")}
            return None
        return {"type": "error", "error": tr(client.lang, "unknown_message", kind=kind)}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.mount("/renders", StaticFiles(directory=renders_dir()), name="renders")
    return app


async def _pump(ws: WebSocket, queue: asyncio.Queue) -> None:
    while True:
        message = await queue.get()
        await ws.send_json(message)


def serve(open_browser: bool = False) -> None:
    import threading
    import webbrowser

    import uvicorn

    settings = Settings.from_env()
    app = create_app(settings)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(settings.url)).start()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info", ws_ping_interval=20, ws_ping_timeout=20)
