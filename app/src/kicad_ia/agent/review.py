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

_POWER_NET = re.compile(r"^(A|D|P)?(GND|VSS|VCC|VDD|VEE|VBAT|VIN|VBUS|VSYS|VREF)\w*$|^[+-]|^\d+V\d*$|V\d", re.I)
_FORBIDDEN_S3 = re.compile(r"\bIO\s*3[567]\b|GPIO\s*3[567]\b", re.I)
_ENABLE_PIN = re.compile(r"^(EN|ENABLE|CE|SHDN|/SHDN)$", re.I)
_R8 = re.compile(r"\bR8\b|PSRAM", re.I)
_ESP32 = re.compile(r"ESP32", re.I)
_REGULATOR = re.compile(r"LDO|REGULATOR|AP2112|AMS1117|MIC52|TLV7|NCP11|LP29", re.I)


class CircuitReviewer:
    def __init__(self, client, limit: int = MAX_REJECTIONS) -> None:
        self._client = client
        self._limit = limit
        self.rejections = 0
        self.note: dict = {}
        self.last_usage = None

    def gate(self, arguments: dict, gateway) -> dict | None:
        """None deja escribir. Un dict se devuelve al modelo y no se toca el archivo."""
        self.note = {}
        self.last_usage = None
        hard = _hard_block(arguments, gateway)
        if hard is not None:
            self.rejections += 1
            return {
                "ok": False,
                "written": False,
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
        self.last_usage = getattr(reply, "usage", None)
        return _verdict(reply)


def _hard_block(arguments: dict, gateway) -> list[str] | None:
    """Reglas eléctricas sin modelo. None = pasan; lista = problemas."""
    symbols = [spec for spec in (arguments.get("symbols") or []) if isinstance(spec, dict)]
    nets = [net for net in (arguments.get("nets") or []) if isinstance(net, dict)]
    if not symbols:
        return None
    problems: list[str] = []
    pin_index = _pin_index(symbols, gateway)
    problems.extend(_unknown_pins(symbols, nets, pin_index))
    problems.extend(_power_in_unconnected(symbols, nets, pin_index))
    problems.extend(_esp32_en_pullup(symbols, nets, pin_index))
    problems.extend(_esp32_s3_r8_io(symbols, nets))
    problems.extend(_regulator_enable_to_output(symbols, nets, pin_index))
    return problems[:6] or None


def _pin_index(symbols: list[dict], gateway) -> dict[str, dict]:
    """reference → {numbers, names, by_number, by_name, types, library}."""
    index = {}
    for spec in symbols:
        ref = str(spec.get("reference") or "")
        lib_id = str(spec.get("lib_id") or "")
        described = gateway.describe_part(lib_id) if lib_id else {"ok": False}
        part = described.get("part") if described.get("ok") else {}
        pins = _pins(part if isinstance(part, dict) else {})
        by_number = {str(pin["number"]): pin for pin in pins if pin.get("number") is not None}
        by_name = {str(pin["name"]).casefold(): pin for pin in pins if pin.get("name")}
        index[ref] = {
            "numbers": set(by_number),
            "names": set(by_name),
            "by_number": by_number,
            "by_name": by_name,
            "lib_id": lib_id,
            "value": str(spec.get("value") or part.get("value") or ""),
            "pins": pins,
        }
    return index


def _unknown_pins(symbols: list[dict], nets: list[dict], pin_index: dict) -> list[str]:
    problems = []
    for net in nets:
        for member in net.get("pins") or []:
            ref = str(member.get("reference") or "")
            pin = str(member.get("pin") or "")
            info = pin_index.get(ref)
            if info is None:
                continue
            if pin in info["numbers"] or pin.casefold() in info["names"]:
                continue
            problems.append(f"{ref}: el pin {pin} no está en la biblioteca.")
    return problems


def _power_in_unconnected(symbols: list[dict], nets: list[dict], pin_index: dict) -> list[str]:
    connected: set[tuple[str, str]] = set()
    for net in nets:
        for member in net.get("pins") or []:
            ref = str(member.get("reference") or "")
            pin = str(member.get("pin") or "")
            connected.add((ref, pin))
            info = pin_index.get(ref) or {}
            by_name = (info.get("by_name") or {}).get(pin.casefold())
            if by_name:
                connected.add((ref, str(by_name["number"])))
    problems = []
    for ref, info in pin_index.items():
        for pin in info["pins"]:
            if str(pin.get("type") or "").casefold() != "power_in":
                continue
            number = str(pin.get("number") or "")
            name = str(pin.get("name") or "")
            if (ref, number) in connected or (ref, name) in connected:
                continue
            problems.append(f"{ref}: el pin de alimentación {name or number} no está en ninguna red.")
    return problems


def _esp32_en_pullup(symbols: list[dict], nets: list[dict], pin_index: dict) -> list[str]:
    problems = []
    for ref, info in pin_index.items():
        blob = f"{info['lib_id']} {info['value']}"
        if not _ESP32.search(blob):
            continue
        en = next((pin for pin in info["pins"] if _ENABLE_PIN.match(str(pin.get("name") or ""))), None)
        if en is None:
            continue
        net = _net_for(ref, str(en["number"]), nets, pin_index) or _net_for(ref, str(en["name"]), nets, pin_index)
        if net is None:
            problems.append(f"{ref}: el pin EN no está en ninguna red; necesita pull-up a 3V3.")
            continue
        name = str(net.get("name") or "")
        if _is_positive_rail(name):
            continue
        # Pull-up: otra pieza (R*) en la misma red y esa red o la otra pata a 3V3.
        others = [
            member
            for member in net.get("pins") or []
            if str(member.get("reference") or "") != ref
        ]
        if any(_is_positive_rail(str(member.get("pin") or "")) for member in others):
            continue
        resistor_refs = [str(m.get("reference") or "") for m in others if str(m.get("reference") or "").upper().startswith("R")]
        if resistor_refs and any(_resistor_to_rail(r, nets, pin_index) for r in resistor_refs):
            continue
        problems.append(f"{ref}: el pin EN no tiene pull-up a 3V3.")
    return problems


def _esp32_s3_r8_io(symbols: list[dict], nets: list[dict]) -> list[str]:
    problems = []
    for spec in symbols:
        value = str(spec.get("value") or "")
        lib_id = str(spec.get("lib_id") or "")
        blob = f"{lib_id} {value}"
        if not (_ESP32.search(blob) and "S3" in blob.upper() and _R8.search(value)):
            continue
        ref = str(spec.get("reference") or "")
        for net in nets:
            for member in net.get("pins") or []:
                if str(member.get("reference") or "") != ref:
                    continue
                pin = str(member.get("pin") or "")
                if _FORBIDDEN_S3.search(pin) or pin in {"35", "36", "37"}:
                    problems.append(f"{ref}: en ESP32-S3 con PSRAM octal no uses IO35/IO36/IO37 (pin {pin}).")
            if _FORBIDDEN_S3.search(str(net.get("name") or "")):
                refs = {str(m.get("reference") or "") for m in net.get("pins") or []}
                if ref in refs:
                    problems.append(f"{ref}: la red {net.get('name')} usa un GPIO prohibido en S3 R8.")
    return problems


def _regulator_enable_to_output(symbols: list[dict], nets: list[dict], pin_index: dict) -> list[str]:
    problems = []
    for ref, info in pin_index.items():
        blob = f"{info['lib_id']} {info['value']}"
        if not _REGULATOR.search(blob):
            continue
        enable = next((pin for pin in info["pins"] if _ENABLE_PIN.match(str(pin.get("name") or ""))), None)
        outputs = [pin for pin in info["pins"] if str(pin.get("type") or "").casefold() == "power_out"]
        if enable is None or not outputs:
            continue
        en_net = _net_for(ref, str(enable["number"]), nets, pin_index)
        if en_net is None:
            continue
        for out in outputs:
            out_net = _net_for(ref, str(out["number"]), nets, pin_index)
            if out_net is not None and out_net is en_net:
                problems.append(
                    f"{ref}: el pin {enable.get('name')} está atado a la salida "
                    f"{out.get('name') or out.get('number')}; debe ir a la entrada o a una señal de enable."
                )
    return problems


def _net_for(ref: str, pin: str, nets: list[dict], pin_index: dict) -> dict | None:
    needle = pin.casefold()
    info = pin_index.get(ref) or {}
    aliases = {needle}
    if pin in (info.get("numbers") or set()):
        aliases.add(pin)
        name = (info.get("by_number") or {}).get(pin, {}).get("name")
        if name:
            aliases.add(str(name).casefold())
    named = (info.get("by_name") or {}).get(needle)
    if named:
        aliases.add(str(named.get("number") or "").casefold())
    for net in nets:
        for member in net.get("pins") or []:
            if str(member.get("reference") or "") != ref:
                continue
            if str(member.get("pin") or "").casefold() in aliases:
                return net
    return None


def _is_positive_rail(name: str) -> bool:
    text = name.strip().casefold()
    if not text or text.startswith("gnd") or text.startswith("vss"):
        return False
    return bool(_POWER_NET.search(name)) and "gnd" not in text and "vss" not in text


def _resistor_to_rail(ref: str, nets: list[dict], pin_index: dict) -> bool:
    for net in nets:
        members = [m for m in net.get("pins") or [] if str(m.get("reference") or "") == ref]
        if not members:
            continue
        if _is_positive_rail(str(net.get("name") or "")):
            return True
    return False


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
