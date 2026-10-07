"""Compactación del historial: acorta resultados de tools de turnos ya cerrados.

El turno en curso se deja intacto (el modelo aún necesita pines de describe_part).
Los pares assistant.tool_calls / tool se conservan; solo se reduce el content.
"""

from __future__ import annotations

import json

# Campos que bastan para no rehacer trabajo en un turno posterior.
_KEEP = (
    "ok",
    "error",
    "decision",
    "intent",
    "review",
    "written",
    "applied",
    "candidate_id",
    "lib_id",
    "selected",
    "footprint",
    "references",
    "reused",
    "needs_selection",
    "problems",
    "verdict",
    "deduplicated",
    "note",
    "auto_groups",
    "draw_frames",
    "eligible",
    "ambiguous",
    "reasons",
    "groups",
    "paper",
)


def compact_closed_turns(messages: list[dict]) -> list[dict]:
    """Resume todos los mensajes tool del historial.

    Se llama al empezar un turno nuevo, antes de añadir el mensaje del usuario:
    entonces toda la conversación previa está cerrada. El turno en curso no se
    vuelve a compactar porque esta función no se invoca entre rondas.
    """
    if not messages:
        return messages
    out = []
    for message in messages:
        if message.get("role") != "tool":
            out.append(message)
            continue
        out.append({**message, "content": _summarize(message.get("content"))})
    return out


def _summarize(content) -> str:
    raw = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return json.dumps({"ok": True, "compacted": True, "preview": (raw or "")[:200]}, ensure_ascii=False)
    if not isinstance(data, dict):
        return json.dumps({"ok": True, "compacted": True}, ensure_ascii=False)
    kept = {key: data[key] for key in _KEEP if key in data}
    kept["compacted"] = True
    if "ok" not in kept:
        kept["ok"] = bool(data.get("ok", True))
    # Identificadores útiles que a veces anidan.
    part = data.get("part") if isinstance(data.get("part"), dict) else None
    if part and "lib_id" not in kept and part.get("lib_id"):
        kept["lib_id"] = part["lib_id"]
    chosen = data.get("chosen") if isinstance(data.get("chosen"), dict) else None
    if chosen:
        if "lib_id" not in kept and chosen.get("lib_id"):
            kept["lib_id"] = chosen["lib_id"]
        if "footprint" not in kept and chosen.get("footprint"):
            kept["footprint"] = chosen["footprint"]
    return json.dumps(kept, ensure_ascii=False)


def tool_key(name: str, arguments: dict) -> str:
    """Clave canónica para deduplicar tool+args en el mismo turno."""
    return name + "\0" + json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False)
