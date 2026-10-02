"""Turnos de chat fuera del bucle del servidor. Cada paso sale como evento."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from kicad_ia.agent.dispatch import ChatBook, dispatch
from kicad_ia.agent.llm import USAGE
from kicad_ia.agent.sessions import SessionStore
from kicad_ia.config import Settings
from kicad_ia.events import SESSIONS, TURN_FAILED, TURN_FINISHED, TURN_STARTED, Event, EventBus
from kicad_ia.tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        settings: Settings,
        gateway,
        registry: ToolRegistry,
        client,
        bus: EventBus,
        book: ChatBook | None = None,
        on_turn_end=None,
        store: SessionStore | None = None,
    ) -> None:
        self._settings = settings
        self._gateway = gateway
        self._registry = registry
        self._client = client
        self._bus = bus
        self._store = store if store is not None else SessionStore()
        self.book = book or ChatBook(store=self._store)
        if book is not None and book.store is None:
            book.store = self._store
        self._on_turn_end = on_turn_end
        self._busy: set[str] = set()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat-turn")

    def session_id(self, wanted: str | None) -> str:
        return self.book.session(wanted).id

    def busy(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._busy

    def submit(self, session_id: str, text: str) -> str | None:
        """Devuelve el id del turno, o None si la sesión ya tiene uno en marcha."""
        session = self.book.session(session_id)
        with self._lock:
            if session.id in self._busy:
                return None
            self._busy.add(session.id)
        turn_id = uuid.uuid4().hex[:12]
        self._bus.publish(Event(TURN_STARTED, {"session_id": session.id, "turn_id": turn_id, "text": text}, target=session.id))
        self._executor.submit(self._run, session, turn_id, text)
        return turn_id

    def apply_runtime(self, settings: Settings, client) -> None:
        """Actualiza LLM/ajustes sin reiniciar el servidor."""
        with self._lock:
            self._settings = settings
            self._client = client

    def summaries(self) -> list[dict]:
        return self._store.summaries() if self._store is not None else []

    def forget(self, session_id: str) -> bool:
        self.book.sessions.pop(session_id, None)
        return self._store.delete(session_id) if self._store is not None else False

    def run_sync(self, session_id: str | None, text: str) -> dict:
        session = self.book.session(session_id)
        payload = dispatch(text, session, self._settings, self._gateway, self._registry, self._client)
        self._remember(session)
        return payload

    def _remember(self, session) -> None:
        if self._store is None or not self._store.save(session):
            return
        self._bus.publish(Event(SESSIONS, {"sessions": self._store.summaries()}))

    def history(self, session_id: str) -> list[dict]:
        session = self.book.sessions.get(session_id)
        if session is None:
            return []
        rows = []
        for message in session.messages:
            role = message.get("role")
            content = message.get("content")
            if role == "user" and content:
                rows.append({"role": "user", "text": content})
            elif role == "assistant" and content:
                rows.append({"role": "assistant", "text": content})
            elif role == "tool" and content:
                try:
                    result = json.loads(content)
                except ValueError:
                    continue
                if isinstance(result, dict) and result.get("image"):
                    rows.append({"role": "image", "image": result["image"]})
        return rows

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self, session, turn_id: str, text: str) -> None:
        base = {"session_id": session.id, "turn_id": turn_id}

        def emit(kind: str, data: dict) -> None:
            self._bus.publish(Event(kind, {**base, **data}, target=session.id))

        try:
            payload = dispatch(text, session, self._settings, self._gateway, self._registry, self._client, emit)
            self._remember(session)
            self._bus.publish(
                Event(
                    TURN_FINISHED,
                    {**base, "reply": payload["reply"], "steps": payload["steps"], "tokens": USAGE.snapshot()},
                    target=session.id,
                )
            )
        except Exception as exc:
            log.exception("Falló un turno de chat")
            self._bus.publish(Event(TURN_FAILED, {**base, "error": str(exc)}, target=session.id))
        finally:
            with self._lock:
                self._busy.discard(session.id)
            if self._on_turn_end is not None:
                self._on_turn_end()
