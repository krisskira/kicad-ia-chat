"""Reparte los eventos del bus a los WebSocket abiertos.

El bus publica desde cualquier hilo; el hub pasa cada evento al bucle de asyncio.
Los eventos con target van solo a los clientes de esa sesión de chat.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field

from kicad_ia.events import SELECTION, STATUS, Event, EventBus

QUEUE_LIMIT = 200


@dataclass
class Client:
    id: int
    session_id: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(QUEUE_LIMIT))


class Hub:
    def __init__(self, bus: EventBus) -> None:
        self._clients: dict[int, Client] = {}
        self._ids = itertools.count(1)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.snapshot: dict[str, dict] = {}
        self._unsubscribe = bus.subscribe(self._on_event)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def close(self) -> None:
        self._unsubscribe()

    def connect(self, session_id: str) -> Client:
        client = Client(next(self._ids), session_id)
        self._clients[client.id] = client
        return client

    def disconnect(self, client: Client) -> None:
        self._clients.pop(client.id, None)

    def move(self, client: Client, session_id: str) -> None:
        client.session_id = session_id

    @property
    def count(self) -> int:
        return len(self._clients)

    def _on_event(self, event: Event) -> None:
        if event.type in (STATUS, SELECTION):
            self.snapshot[event.type] = event.data
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._deliver, event)

    def _deliver(self, event: Event) -> None:
        message = event.message()
        for client in list(self._clients.values()):
            if event.target is not None and event.target != client.session_id:
                continue
            if client.queue.full():
                try:
                    client.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            client.queue.put_nowait(message)
