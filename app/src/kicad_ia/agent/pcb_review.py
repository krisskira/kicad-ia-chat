"""Revisor de placa: interpreta DRC/IPC tras colocación o autoruteo."""

from __future__ import annotations

import json
import re

from kicad_ia.agent.llm import LlmReply

MAX_REJECTIONS = 2

_SYSTEM = """Eres el revisor de PCB de KiCad IA. No escribes archivos.
Recibes un informe determinista (DRC de KiCad + pre-chequeo IPC Clase 2) y métricas.
Responde solo con la herramienta verdict, en español.

RECHAZA siempre si:
- Hay errores DRC duros nuevos (drc.error_count mayor que baseline_drc_errors).
  Los errores que ya estaban antes (preexisting_drc) no bloquean: menciónalos como aviso.
- Quedan redes sin rutear (unconnected > 0) cuando la operación era autoruteo.
- El candidato empeora el score respecto al baseline (better_than false).
- Componentes se solapan o salen del contorno.

Puedes APROBAR con avisos si solo hay warnings IPC informativos y el DRC está limpio.
Como máximo 8 problemas, cada uno concreto (referencia, red o regla).
Aclara que es un pre-chequeo, no una certificación IPC.
"""

_VERDICT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "verdict",
            "description": "Aprueba o rechaza el resultado de placa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "approved": {"type": "boolean"},
                    "problems": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                },
                "required": ["approved"],
            },
        },
    }
]


class PcbReviewer:
    def __init__(self, client, limit: int = MAX_REJECTIONS) -> None:
        self._client = client
        self._limit = limit
        self.rejections = 0
        self.note: dict = {}

    def gate(self, report: dict) -> dict | None:
        """None = aprobado. Dict = bloqueo para el modelo."""
        self.note = {}
        hard = _hard_block(report)
        if hard is not None:
            self.rejections += 1
            return {
                "ok": False,
                "applied": False,
                "review": "rejected" if self.rejections < self._limit else "exhausted",
                "problems": hard,
                "attempts_left": max(0, self._limit - self.rejections),
            }
        if self._client is None:
            self.note = {"review": "approved", "review_note": "Sin modelo revisor; pasan solo las reglas duras."}
            return None
        if self.rejections >= self._limit:
            return {
                "ok": False,
                "applied": False,
                "review": "exhausted",
                "error": f"El revisor de PCB rechazó el resultado {self._limit} veces. No aplico cambios.",
            }
        try:
            verdict = self._review(report)
        except Exception as exc:
            self.note = {"review": "skipped", "review_error": str(exc)}
            return None
        if verdict["approved"]:
            self.note = {"review": "approved", "summary": verdict.get("summary") or ""}
            return None
        self.rejections += 1
        return {
            "ok": False,
            "applied": False,
            "review": "rejected",
            "problems": verdict["problems"],
            "attempts_left": self._limit - self.rejections,
        }

    def _review(self, report: dict) -> dict:
        payload = json.dumps(report, ensure_ascii=False)[:12000]
        reply = self._client.complete([{"role": "user", "content": payload}], _VERDICT_TOOL, _SYSTEM)
        return _verdict(reply)


def _hard_block(report: dict) -> list[str] | None:
    problems = []
    drc = report.get("drc") or {}
    errors = int(drc.get("error_count") or 0)
    if errors > int(report.get("baseline_drc_errors") or 0):
        problems.extend((drc.get("problems") or [])[:5] or ["Hay errores DRC."])
    if report.get("operation") == "autoroute" and int(drc.get("unconnected") or report.get("unconnected") or 0) > 0:
        problems.append(f"Quedan {drc.get('unconnected') or report.get('unconnected')} redes sin rutear.")
    score = report.get("score") or {}
    baseline = report.get("baseline_score") or {}
    if baseline and score and not report.get("better_than", True):
        problems.append(
            f"El candidato empeora el resultado (score {score.get('score')} vs {baseline.get('score')}, "
            f"errores {score.get('errors')} vs {baseline.get('errors')})."
        )
    ipc_errors = [f for f in report.get("ipc_findings") or [] if f.get("severity") == "error"]
    for item in ipc_errors[:4]:
        problems.append(item.get("message") or item.get("code") or "Error IPC.")
    return problems or None


def _verdict(reply: LlmReply) -> dict:
    for call in reply.tool_calls:
        if call.name == "verdict":
            return _normalize(call.arguments)
    found = re.search(r"\{.*\}", reply.content or "", re.S)
    if not found:
        return {"approved": False, "problems": ["El revisor de PCB no dio un veredicto."], "summary": ""}
    try:
        return _normalize(json.loads(found.group(0)))
    except json.JSONDecodeError:
        return {"approved": False, "problems": ["El revisor de PCB no dio un veredicto."], "summary": ""}


def _normalize(data: dict) -> dict:
    if data.get("approved") is True:
        return {"approved": True, "problems": [], "summary": str(data.get("summary") or "")}
    problems = [str(item).strip() for item in data.get("problems") or [] if str(item).strip()]
    return {
        "approved": False,
        "problems": problems[:8] or ["El revisor no aprobó el resultado de placa."],
        "summary": str(data.get("summary") or ""),
    }
