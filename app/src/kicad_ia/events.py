"""Bus de eventos del proceso. Los servicios publican; el servidor reparte a los navegadores."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

STATUS = "status"
SELECTION = "selection"
TURN_STARTED = "turn.started"
TURN_FINISHED = "turn.finished"
TURN_FAILED = "turn.failed"
TOOL_STARTED = "tool.started"
TOOL_FINISHED = "tool.finished"
LLM_ROUND = "llm.round"
LLM_TEXT = "llm.text"


@dataclass(frozen=True)
class Event:
    type: str
    data: dict = field(default_factory=dict)
    target: str | None = None

    def message(self) -> dict:
        return {"type": self.type, **self.data}


Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self._lock = threading.Lock()

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        with self._lock:
            self._handlers.append(handler)

        def unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers:
                    self._handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._handlers)
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                log.exception("Fallo un suscriptor de %s", event.type)
