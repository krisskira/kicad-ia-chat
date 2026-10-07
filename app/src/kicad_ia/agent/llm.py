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
        self._estimated = False

    def add(self, usage) -> None:
        """Suma el `usage` de una respuesta. Si viene vacío o en cero, no cuenta."""
        prompt, completion, reported, _cached = parse_usage_detail({"usage": usage} if isinstance(usage, dict) else {})
        with self._lock:
            self._calls += 1
            if not reported:
                return
            self._prompt += prompt
            self._completion += completion
            self._reported = True

    def add_estimate(self, prompt: int, completion: int) -> None:
        """Cuando el proveedor no informa consumo. La UI lo marca con ~."""
        with self._lock:
            self._calls += 1
            self._prompt += max(0, prompt)
            self._completion += max(0, completion)
            self._estimated = True

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "prompt": self._prompt,
                "completion": self._completion,
                "total": self._prompt + self._completion,
                "calls": self._calls,
                "reported": self._reported,
                "estimated": self._estimated and not self._reported,
            }


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _first_int(data: dict, *keys: str) -> int:
    for key in keys:
        number = _as_int(data.get(key))
        if number:
            return number
    return 0


def parse_usage(body: dict) -> tuple[int, int, bool]:
    """Lee el consumo venga como lo mande el proveedor. Compatible con el API antiguo."""
    prompt, completion, reported, _cached = parse_usage_detail(body)
    return prompt, completion, reported


def parse_usage_detail(body: dict) -> tuple[int, int, bool, int]:
    """Devuelve prompt, completion, reported y tokens de entrada en caché."""
    if not isinstance(body, dict):
        return 0, 0, False, 0
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    meta = body.get("usageMetadata") or body.get("usage_metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    prompt = _first_int(usage, "prompt_tokens", "input_tokens", "promptTokenCount") or _first_int(
        meta, "promptTokenCount", "prompt_token_count"
    )
    completion = _first_int(
        usage, "completion_tokens", "output_tokens", "candidatesTokenCount", "completionTokenCount"
    ) or _first_int(meta, "candidatesTokenCount", "candidates_token_count", "completionTokenCount")
    details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    cached = _first_int(details, "cached_tokens", "cachedTokenCount") or _first_int(
        meta, "cachedContentTokenCount", "cached_content_token_count"
    )
    if prompt or completion:
        return prompt, completion, True, cached
    total = _first_int(usage, "total_tokens", "totalTokenCount") or _first_int(meta, "totalTokenCount", "total_token_count")
    if total:
        return total, 0, True, cached
    return 0, 0, False, 0


def rough_tokens(value) -> int:
    """Aproximación de 4 caracteres por token. Solo se usa si no hay usage."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return max(1, len(text) // 4) if text else 0


USAGE = TokenMeter()


def retry_delay(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after", "")
    if header.replace(".", "", 1).isdigit():
        return float(header)
    found = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', response.text)
    return float(found.group(1)) if found else None


@dataclass
class CallUsage:
    prompt: int = 0
    completion: int = 0
    total: int = 0
    cached: int = 0
    reported: bool = False
    estimated: bool = False
    model: str = ""
    role: str = "main"

    def as_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total or (self.prompt + self.completion),
            "cached": self.cached,
            "reported": self.reported,
            "estimated": self.estimated,
            "model": self.model,
            "role": self.role,
        }


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
    usage: CallUsage | None = None

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
    def __init__(self, settings: Settings, model: str = "", role: str = "main") -> None:
        self._settings = settings
        self._model = model or settings.llm_model
        self.role = role

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
        message = body["choices"][0]["message"]
        prompt, completion, reported, cached = parse_usage_detail(body)
        if reported:
            USAGE.add({"prompt_tokens": prompt, "completion_tokens": completion})
            usage = CallUsage(
                prompt=prompt,
                completion=completion,
                total=prompt + completion,
                cached=cached,
                reported=True,
                model=self._model,
                role=self.role,
            )
        else:
            outgoing = rough_tokens([{"role": "system", "content": system}, *messages])
            incoming = rough_tokens(message.get("content") or "") + rough_tokens(message.get("tool_calls") or "")
            USAGE.add_estimate(outgoing, incoming)
            usage = CallUsage(
                prompt=outgoing,
                completion=incoming,
                total=outgoing + incoming,
                estimated=True,
                model=self._model,
                role=self.role,
            )
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
        return LlmReply(content=message.get("content") or "", tool_calls=calls, usage=usage)


class ScriptedClient:
    """Cliente fijo para pruebas del bucle de herramientas."""

    def __init__(self, replies: list[LlmReply], role: str = "main") -> None:
        self._replies = list(replies)
        self.seen: list[list[dict]] = []
        self.role = role

    def complete(self, messages: list[dict], tools: list[dict], system: str) -> LlmReply:
        del tools, system
        self.seen.append(messages)
        if not self._replies:
            return LlmReply(content="Sin más respuestas de prueba.", usage=CallUsage(role=self.role, estimated=True))
        reply = self._replies.pop(0)
        if reply.usage is None:
            reply.usage = CallUsage(role=self.role, estimated=True, model="scripted")
        return reply
