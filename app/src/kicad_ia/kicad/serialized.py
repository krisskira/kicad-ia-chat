"""Un solo hilo a la vez habla con KiCad: el cliente de kipy no es seguro entre hilos."""

from __future__ import annotations

import threading


class SerializedGateway:
    def __init__(self, inner) -> None:
        self._inner = inner
        self._lock = threading.RLock()

    @property
    def inner(self):
        return self._inner

    def swap(self, inner) -> None:
        with self._lock:
            self._inner = inner

    def __getattr__(self, name: str):
        value = getattr(self._inner, name)
        if not callable(value):
            return value

        def locked(*args, **kwargs):
            with self._lock:
                return getattr(self._inner, name)(*args, **kwargs)

        return locked
