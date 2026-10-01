"""Cola de candidatos de placa (colocación / autoruteo) para confirmar apply.

Flujo: operación con apply=false → se guarda un CandidateJob con id →
el usuario confirma → apply=true + candidate_id aplica el resultado a la placa viva.
Los jobs caducan tras ttl_s (por defecto 1 h).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CandidateJob:
    id: str
    kind: str  # place | route | validate
    created: float
    project: str
    files: dict = field(default_factory=dict)
    placements: list = field(default_factory=list)
    report: dict = field(default_factory=dict)
    approved: bool = False


class CandidateStore:
    def __init__(self, ttl_s: float = 3600) -> None:
        self._ttl = ttl_s
        self._items: dict[str, CandidateJob] = {}
        self._lock = threading.Lock()

    def put(self, kind: str, project: str, **payload) -> CandidateJob:
        self._purge()
        job = CandidateJob(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            created=time.time(),
            project=project,
            files=payload.get("files") or {},
            placements=payload.get("placements") or [],
            report=payload.get("report") or {},
            approved=bool(payload.get("approved")),
        )
        with self._lock:
            self._items[job.id] = job
        return job

    def get(self, job_id: str) -> CandidateJob | None:
        self._purge()
        with self._lock:
            return self._items.get(job_id)

    def drop(self, job_id: str) -> None:
        with self._lock:
            self._items.pop(job_id, None)

    def _purge(self) -> None:
        now = time.time()
        with self._lock:
            dead = [key for key, job in self._items.items() if now - job.created > self._ttl]
            for key in dead:
                job = self._items.pop(key)
                for path in job.files.values():
                    try:
                        Path(path).unlink(missing_ok=True)
                    except Exception:
                        pass


STORE = CandidateStore()
