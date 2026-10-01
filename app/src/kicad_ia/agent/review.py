"""Revisor eléctrico: mira la propuesta antes de escribir el esquemático."""

from __future__ import annotations

import json
import re

from kicad_ia.agent.llm import LlmReply

MAX_REJECTIONS = 2

_SYSTEM = """Eres el revisor eléctrico de un esquemático de KiCad. No escribes archivos.
Recibes símbolos propuestos y los pines reales de la biblioteca, más las redes.
Responde solo con la herramienta verdict, en español.

Rechaza si ocurre alguno de estos casos:
- El enable de un regulador no va a su entrada (o a una señal que la encienda). Atarlo a la salida lo deja apagado.
- El pin EN de un módulo ESP32 no tiene pull-up a 3V3.
- Una señal une un solo extremo, o un pin de alimentación power_in no está en ninguna red.
- En un ESP32-S3 con PSRAM octal (R8 en el valor) se usan IO35, IO36 o IO37.
- Una huella no existe o el número de pin no está en la lista real.

Aprueba si el diseño es razonable aunque queden pines sin usar. Como máximo 6 problemas, cada uno en una frase que diga la referencia y el pin.
"""

_VERDICT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "verdict",
            "description": "Aprueba el diseño o enumera los problemas eléctricos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "approved": {"type": "boolean"},
                    "problems": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["approved"],
            },
        },
    }
]


class CircuitReviewer:
    def __init__(self, client, limit: int = MAX_REJECTIONS) -> None:
        self._client = client
        self._limit = limit
        self.rejections = 0
        self.note: dict = {}

    def gate(self, arguments: dict, gateway) -> dict | None:
        """None deja escribir. Un dict se devuelve al modelo y no se toca el archivo."""
        self.note = {}
        if self.rejections >= self._limit:
            return {
                "ok": False,
                "written": False,
                "review": "exhausted",
                "error": (
                    f"El revisor rechazó el diseño {self._limit} veces en este mensaje. "
                    "No escribo el esquemático. Explica los problemas y espera la decisión del usuario."
                ),
            }
        try:
            verdict = self._review(arguments, gateway)
        except Exception as exc:
            self.note = {"review": "skipped", "review_error": str(exc)}
            return None
        if verdict["approved"]:
            self.note = {"review": "approved"}
            return None
        self.rejections += 1
        return {
            "ok": False,
            "written": False,
            "review": "rejected",
            "problems": verdict["problems"],
            "attempts_left": self._limit - self.rejections,
        }

    def _review(self, arguments: dict, gateway) -> dict:
        parts = []
        for spec in arguments.get("symbols") or []:
            described = gateway.describe_part(str(spec.get("lib_id") or ""))
            library = described.get("part") if described.get("ok") else {"error": described.get("error", "")}
            parts.append({"proposed": spec, "pins": _pins(library), "default_footprint": library.get("footprint", "")})
        payload = json.dumps({"symbols": parts, "nets": arguments.get("nets") or []}, ensure_ascii=False)
        reply = self._client.complete([{"role": "user", "content": payload}], _VERDICT_TOOL, _SYSTEM)
        return _verdict(reply)


def _pins(library: dict) -> list[dict]:
    return [
        {"number": pin.get("number"), "name": pin.get("name"), "type": pin.get("type")}
        for pin in library.get("pins") or []
    ]


def _verdict(reply: LlmReply) -> dict:
    for call in reply.tool_calls:
        if call.name == "verdict":
            return _normalize(call.arguments)
    found = re.search(r"\{.*\}", reply.content or "", re.S)
    if not found:
        return {"approved": False, "problems": ["El revisor no dio un veredicto."]}
    try:
        return _normalize(json.loads(found.group(0)))
    except json.JSONDecodeError:
        return {"approved": False, "problems": ["El revisor no dio un veredicto."]}


def _normalize(data: dict) -> dict:
    if data.get("approved") is True:
        return {"approved": True, "problems": []}
    problems = [str(item).strip() for item in data.get("problems") or [] if str(item).strip()]
    return {"approved": False, "problems": problems[:6] or ["El revisor no aprobó el diseño."]}
