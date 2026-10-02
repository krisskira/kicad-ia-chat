"""Conversaciones en disco, para volver a abrirlas después de cerrar el chat.

Cada sesión es un JSON en el directorio de ajustes (`sessions/`). No guarda
claves de API: solo mensajes, contrato de intención y piezas ya aceptadas.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from kicad_ia.agent.intent import DesignMemory
from kicad_ia.agent.loop import Session
from kicad_ia.user_prefs import prefs_dir

TITLE_LIMIT = 48


def sessions_dir() -> Path:
    root = prefs_dir() / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _title_from(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user" and str(message.get("content") or "").strip():
            text = " ".join(str(message["content"]).split())
            return text[:TITLE_LIMIT]
    return ""


def session_to_dict(session: Session) -> dict:
    memory = session.memory if isinstance(session.memory, DesignMemory) else DesignMemory()
    return {
        "id": session.id,
        "title": session.title or _title_from(session.messages),
        "updated": session.updated or _now(),
        "messages": session.messages,
        "memory": memory.to_dict(),
    }


def session_from_dict(data: dict) -> Session:
    session = Session(
        id=str(data.get("id") or ""),
        messages=list(data.get("messages") or []),
        title=str(data.get("title") or ""),
        updated=str(data.get("updated") or ""),
    )
    session.memory = DesignMemory.from_dict(data.get("memory") or {})
    return session


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or sessions_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, session_id: str) -> Path:
        safe = "".join(char for char in session_id if char.isalnum())
        return self.root / f"{safe}.json"

    def save(self, session: Session) -> bool:
        title = _title_from(session.messages)
        if not title:
            return False
        session.title = session.title or title
        session.updated = _now()
        payload = session_to_dict(session)
        self.path_for(session.id).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return True

    def load(self, session_id: str) -> Session | None:
        path = self.path_for(session_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not data.get("id"):
            return None
        return session_from_dict(data)

    def delete(self, session_id: str) -> bool:
        path = self.path_for(session_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def summaries(self) -> list[dict]:
        rows = []
        for path in self.root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict) or not data.get("id"):
                continue
            title = str(data.get("title") or "").strip()
            if not title:
                continue
            rows.append({"id": data["id"], "title": title, "updated": str(data.get("updated") or "")})
        rows.sort(key=lambda row: row["updated"], reverse=True)
        return rows[:80]
