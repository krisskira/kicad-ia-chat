"""Cliente de chat compatible con la API de OpenAI y respuestas de prueba."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field

import httpx

from kicad_ia.config import Settings

ATTEMPTS = 3
MAX_WAIT_S = 30.0
RETRY_STATUS = {429, 500, 502, 503, 504}


class LlmError(RuntimeError):
    pass


class TokenMeter:
    """Tokens que el proveedor dice haber cobrado desde que arrancó el chat.

    Suma el modelo principal y los revisores. Solo cuenta lo que llega en
    `usage`; si el proveedor no lo manda, `reported` queda en False.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prompt = 0
        self._completion = 0
        self._calls = 0
        self._reported = False

    def add(self, usage) -> None:
        with self._lock:
            self._calls += 1
            if not isinstance(usage, dict):
                return
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            total = int(usage.get("total_tokens") or 0)
            if not prompt and not completion and total:
                prompt = total
            self._prompt += prompt
            self._completion += completion
            self._reported = self._reported or bool(prompt or completion)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "prompt": self._prompt,
                "completion": self._completion,
                "total": self._prompt + self._completion,
                "calls": self._calls,
                "reported": self._reported,
            }


USAGE = TokenMeter()


def retry_delay(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after", "")
    if header.replace(".", "", 1).isdigit():
        return float(header)
    found = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', response.text)
    return float(found.group(1)) if found else None


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    extra: dict = field(default_factory=dict)


@dataclass
class LlmReply:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)

    def as_message(self) -> dict:
        message: dict = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    **call.extra,
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in self.tool_calls
            ]
        return message


class OpenAiCompatibleClient:
    def __init__(self, settings: Settings, model: str = "") -> None:
        self._settings = settings
        self._model = model or settings.llm_model

    def complete(self, messages: list[dict], tools: list[dict], system: str) -> LlmReply:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self._settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self._settings.llm_api_key}"

        response = None
        for attempt in range(ATTEMPTS):
            try:
                response = httpx.post(
                    f"{self._settings.llm_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
            except httpx.HTTPError as exc:
                if attempt == ATTEMPTS - 1:
                    raise LlmError(f"No hay conexión con el modelo: {exc}") from exc
                time.sleep(2.0 * (attempt + 1))
                continue
            if response.status_code not in RETRY_STATUS:
                break
            if attempt == ATTEMPTS - 1:
                break
            time.sleep(min(retry_delay(response) or 2.0 * (attempt + 1), MAX_WAIT_S))

        if response is None or response.status_code == 429:
            raise LlmError(
                f"El proveedor del modelo limitó las peticiones (429) con {self._model}. "
                "Espera un minuto o revisa la cuota del proyecto."
            )
        if response.status_code >= 400:
            raise LlmError(f"El modelo respondió {response.status_code}: {response.text[:300]}")

        body = response.json()
        USAGE.add(body.get("usage"))
        message = body["choices"][0]["message"]
        calls = []
        for call in message.get("tool_calls") or []:
            raw = call.get("function", {}).get("arguments") or "{}"
            try:
                arguments = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                arguments = {}
            calls.append(
                ToolCall(
                    id=str(call.get("id") or call["function"]["name"]),
                    name=call["function"]["name"],
                    arguments=arguments if isinstance(arguments, dict) else {},
                    extra={key: value for key, value in call.items() if key not in ("id", "type", "function", "index")},
                )
            )
        return LlmReply(content=message.get("content") or "", tool_calls=calls)


class ScriptedClient:
    """Cliente fijo para pruebas del bucle de herramientas."""

    def __init__(self, replies: list[LlmReply]) -> None:
        self._replies = list(replies)
        self.seen: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict], system: str) -> LlmReply:
        del tools, system
        self.seen.append(messages)
        if not self._replies:
            return LlmReply(content="Sin más respuestas de prueba.")
        return self._replies.pop(0)
