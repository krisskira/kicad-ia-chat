"""Vigila KiCad en un hilo y publica estado y selección solo cuando cambian."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable

from kicad_ia.config import Settings
from kicad_ia.events import SELECTION, STATUS, Event, EventBus
from kicad_ia.kicad.serialized import SerializedGateway

log = logging.getLogger(__name__)

RECONNECT_EVERY_S = 5.0


def status_payload(settings: Settings, gateway) -> dict:
    from kicad_ia.kicad.freerouting import probe_java

    try:
        caps = gateway.capabilities()
    except Exception as exc:
        caps = {"connected": False, "backend": "error", "notes": [str(exc)]}
    java = caps.get("java") if isinstance(caps.get("java"), dict) else probe_java(settings.java_bin)
    return {
        "llm_ready": settings.llm_ready,
        "model": settings.llm_model if settings.llm_ready else "",
        "review_model": settings.llm_review_model,
        "autoroute_enabled": settings.autoroute_enabled,
        "fab": settings.fab_summary(),
        "java": java,
        "capabilities": caps,
    }


def selection_payload(gateway) -> dict:
    try:
        items = gateway.selection()
    except Exception as exc:
        return {"items": [], "error": str(exc)}
    return {"items": items}


class KicadWatcher:
    def __init__(
        self,
        settings: Settings,
        gateway: SerializedGateway,
        bus: EventBus,
        interval: float = 1.5,
        connect: Callable[[], object] | None = None,
    ) -> None:
        self._settings = settings
        self._gateway = gateway
        self._bus = bus
        self._interval = interval
        self._connect = connect
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: dict[str, str] = {}
        self._next_reconnect = 0.0

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="kicad-watcher", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def poke(self, force: bool = False) -> None:
        if force:
            self._last.clear()
        self._wake.set()

    def poll_once(self) -> None:
        self._maybe_reconnect()
        self._publish_if_changed(STATUS, status_payload(self._settings, self._gateway))
        self._publish_if_changed(SELECTION, selection_payload(self._gateway))

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                log.exception("El vigilante de KiCad falló")
            self._wake.wait(self._interval)
            self._wake.clear()

    def _publish_if_changed(self, kind: str, payload: dict) -> None:
        digest = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        if self._last.get(kind) == digest:
            return
        self._last[kind] = digest
        self._bus.publish(Event(kind, payload))

    def _maybe_reconnect(self) -> None:
        if self._connect is None or time.monotonic() < self._next_reconnect:
            return
        inner = self._gateway.inner
        alive = getattr(inner, "alive", None)
        healthy = alive() if callable(alive) else not getattr(inner, "fallback_reason", "")
        if healthy:
            return
        self._next_reconnect = time.monotonic() + RECONNECT_EVERY_S
        try:
            fresh = self._connect()
        except Exception as exc:
            log.debug("KiCad sigue sin responder: %s", exc)
            return
        self._gateway.swap(fresh)
        log.info("Conectado de nuevo a KiCad")
