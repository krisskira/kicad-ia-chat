"""Chat HTTP y atajos que funcionan aunque todavía no haya modelo configurado."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from kicad_ia.agent.llm import OpenAiCompatibleClient
from kicad_ia.agent.loop import Session, Turn, run_turn
from kicad_ia.agent.pcb_review import PcbReviewer
from kicad_ia.agent.review import CircuitReviewer
from kicad_ia.config import Settings
from kicad_ia.i18n import INSPECT_COMMANDS, TOOL_COMMANDS, normalize_lang, tr
from kicad_ia.kicad.gateway import Gateway
from kicad_ia.tools.registry import ToolRegistry


@dataclass
class ChatBook:
    sessions: dict[str, Session] = field(default_factory=dict)
    store: object = None

    def find(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        if session_id in self.sessions:
            return self.sessions[session_id]
        if self.store is None:
            return None
        loaded = self.store.load(session_id)
        if loaded is None:
            return None
        self.sessions[loaded.id] = loaded
        return loaded

    def session(self, session_id: str | None) -> Session:
        found = self.find(session_id)
        if found is not None:
            return found
        created = Session(id=uuid.uuid4().hex)
        self.sessions[created.id] = created
        return created


def dispatch(
    text: str,
    session: Session,
    settings: Settings,
    gateway: Gateway,
    registry: ToolRegistry,
    client,
    emit: Callable[[str, dict], None] | None = None,
    prior: str = "",
    lang: str = "en",
    cancelled: Callable[[], bool] | None = None,
) -> dict:
    lang = normalize_lang(lang)
    cleaned = text.strip()
    if not cleaned:
        return _payload(session, tr(lang, "empty"), [])
    if cleaned in INSPECT_COMMANDS:
        result = registry.call("inspect_context", {}, gateway)
        return _spoken(session, cleaned, _format_inspect(result, lang), [{"tool": "inspect_context", "arguments": {}, "result": result}])
    if cleaned in TOOL_COMMANDS:
        exclude = {"autoroute_board"} if not settings.autoroute_enabled else set()
        names = registry.names(exclude=exclude)
        return _spoken(session, cleaned, tr(lang, "tools", names=", ".join(names)), [{"tool": "list", "arguments": {}, "result": names}])
    if not settings.llm_ready or client is None:
        return _spoken(session, cleaned, tr(lang, "missing_model"), [])
    # El revisor usa la misma URL y clave que el orquestador (cualquier proveedor
    # compatible con OpenAI). Vacío = solo reglas duras en código.
    review_model = settings.llm_review_model
    electrical_client = (
        OpenAiCompatibleClient(settings, model=review_model, role="electrical_review") if review_model else None
    )
    pcb_client = OpenAiCompatibleClient(settings, model=review_model, role="pcb_review") if review_model else None
    reviewer = CircuitReviewer(electrical_client)
    pcb_reviewer = PcbReviewer(pcb_client)

    def shrunk_emit(kind: str, data: dict) -> None:
        emit(kind, shrink_step(data) if "result" in data else data)

    turn: Turn = run_turn(
        session,
        cleaned,
        client,
        registry,
        gateway,
        reviewer,
        shrunk_emit if emit else None,
        pcb_reviewer,
        settings,
        prior,
        lang,
        cancelled,
    )
    return _payload(session, turn.reply, turn.steps, cancelled=turn.cancelled)


def _spoken(session: Session, user_text: str, reply: str, steps: list) -> dict:
    """Atajos que no pasan por el modelo: igual quedan en la conversación guardada."""
    session.messages.append({"role": "user", "content": user_text})
    session.messages.append({"role": "assistant", "content": reply})
    return _payload(session, reply, steps)


def _payload(session: Session, reply: str, steps: list, cancelled: bool = False) -> dict:
    payload = {"session_id": session.id, "reply": reply, "steps": [shrink_step(step) for step in steps]}
    if cancelled:
        payload["cancelled"] = True
    return payload


def _format_inspect(result: dict, lang: str = "en") -> str:
    if not result.get("ok", True) and result.get("error"):
        return str(result["error"])
    selection = result.get("selection") or []
    if not selection:
        selected = tr(lang, "nothing_selected")
    else:
        bits = []
        for item in selection:
            label = item.get("reference") or item.get("kind") or tr(lang, "item")
            editor = item.get("editor") or ""
            bits.append(f"{label} ({editor})" if editor else str(label))
        selected = tr(lang, "selection", items=", ".join(bits))
    schematic = result.get("schematic") or {}
    board = result.get("board") or {}
    symbol_count = schematic.get("symbol_count")
    if symbol_count is None:
        symbol_count = len(schematic.get("symbols") or [])
    footprint_count = board.get("footprint_count")
    if footprint_count is None:
        footprint_count = len(board.get("footprints") or [])
    backend = (result.get("capabilities") or {}).get("backend", "")
    return tr(
        lang,
        "inspect",
        selected=selected,
        symbols=symbol_count,
        footprints=footprint_count,
        backend=backend,
    )


KEPT_KEYS = (
    "ok",
    "error",
    "image",
    "before_image",
    "format",
    "written",
    "review",
    "verdict",
    "candidate_id",
    "applied",
    "better_than",
    "score",
    "disclaimer",
)


def shrink_step(step: dict) -> dict:
    raw = json.dumps(step, ensure_ascii=False)
    if len(raw) <= 4000:
        return step
    result = step.get("result")
    kept = {key: result[key] for key in KEPT_KEYS if isinstance(result, dict) and key in result}
    return {**step, "arguments": step.get("arguments"), "result": {**kept, "truncated": True, "preview": raw[:1500]}}
