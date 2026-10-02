"""Selección de componentes contra las bibliotecas. No inventa piezas ni datos.

Un acierto exacto del número pedido se puede aceptar si la biblioteca lo tiene
y no falla un dato que sí se pudo comprobar. Un sustituto no se acepta solo:
hace falta allow_substitution, un único candidato y ningún dato crítico en
UNKNOWN. Si hay varias opciones, la respuesta es decision_required.
"""

from __future__ import annotations

from kicad_ia.agent.intent import DesignMemory

_ELECTRICAL = ("voltage", "current", "power", "temperature", "tolerance", "frequency")


def select_component(gateway, args: dict, memory: DesignMemory) -> dict:
    requested = str(args.get("requested_part") or "").strip()
    function = str(args.get("function") or "").strip()
    stage = str(args.get("stage") or "").strip()
    queries = [str(item).strip() for item in (args.get("queries") or []) if str(item).strip()]
    hard = args.get("hard") if isinstance(args.get("hard"), dict) else {}
    required_pins = [str(pin) for pin in (args.get("required_pins") or [])]
    architectural = bool(args.get("architectural_change"))
    if not requested and not function and not queries:
        return {"ok": False, "error": "Indica requested_part, function o queries. No inventes un lib_id."}

    exact = _search_exact(gateway, requested) if requested else []
    if exact:
        return _decide_exact(gateway, memory, exact, requested, hard, required_pins, stage, architectural)

    if not function and not queries:
        return {
            "ok": True,
            "decision": "request_user",
            "reason": "component_unavailable",
            "requested": requested,
            "candidates": [],
            "note": (
                "No está en las bibliotecas de KiCad. No deduzco la función ni invento un sustituto. "
                "Pasa function o queries con lo que pidió el usuario, o pregúntale."
            ),
        }

    seen: dict[str, dict] = {}
    for query in [function, *queries]:
        if not query:
            continue
        found = gateway.search_parts("symbol", query, 8)
        for match in found.get("matches") or []:
            lib_id = str(match.get("lib_id") or "")
            if lib_id and lib_id not in seen:
                seen[lib_id] = match
    if not seen:
        return {
            "ok": True,
            "decision": "request_user",
            "reason": "no_candidates",
            "requested": requested,
            "function": function,
            "candidates": [],
            "note": "Ninguna biblioteca devolvió candidatos. No inventes un número de parte.",
        }

    candidates = [
        _evaluate(gateway, match, requested, hard, required_pins, architectural)
        for match in list(seen.values())[:5]
    ]
    viable = [row for row in candidates if row["result"] != "REJECTED"]
    if not viable:
        return {
            "ok": True,
            "decision": "request_user",
            "reason": "not_compatible",
            "classification": "NOT_COMPATIBLE",
            "candidates": candidates,
            "stage": stage,
        }
    if (
        len(viable) == 1
        and args.get("allow_substitution")
        and not architectural
        and not _unknown_hard(viable[0], hard, required_pins)
    ):
        chosen = viable[0]
        _accept_substitution(memory, requested, chosen["lib_id"])
        return {
            "ok": True,
            "decision": "selected",
            "autonomy": "confirmed_substitution",
            "change_set": _change_set(requested, chosen, stage),
            "candidate": chosen,
        }
    reason = "multiple_valid_alternatives" if len(viable) > 1 else "insufficient_information"
    if architectural:
        reason = "architectural_change"
    return {
        "ok": True,
        "decision": "decision_required",
        "reason": reason,
        "autonomy": "propose",
        "requested": requested,
        "function": function,
        "stage": stage,
        "candidates": candidates,
        "note": "No elijas entre estas opciones. Pregunta al usuario o espera allow_substitution con un solo candidato verificable.",
    }


def _search_exact(gateway, requested: str) -> list[dict]:
    found = gateway.search_parts("symbol", requested, 8)
    return [match for match in found.get("matches") or [] if _is_exact(str(match.get("lib_id") or ""), requested)]


def _is_exact(lib_id: str, requested: str) -> bool:
    want = requested.casefold().strip()
    name = lib_id.split(":")[-1].casefold()
    return lib_id.casefold() == want or name == want


def _decide_exact(gateway, memory, matches, requested, hard, required_pins, stage, architectural) -> dict:
    if len(matches) > 1:
        candidates = [_evaluate(gateway, match, requested, hard, required_pins, architectural) for match in matches]
        return {
            "ok": True,
            "decision": "decision_required",
            "reason": "multiple_valid_alternatives",
            "autonomy": "propose",
            "requested": requested,
            "candidates": candidates,
        }
    chosen = _evaluate(gateway, matches[0], requested, hard, required_pins, architectural)
    if chosen["result"] == "REJECTED" or architectural:
        return {
            "ok": True,
            "decision": "request_user",
            "reason": "critical_constraint_conflict" if chosen["result"] == "REJECTED" else "architectural_change",
            "candidate": chosen,
            "stage": stage,
            "note": "No lo uses. El dato comprobado no cumple, o el cambio de arquitectura no puede ser silencioso.",
        }
    if _unknown_hard(chosen, hard, required_pins):
        return {
            "ok": True,
            "decision": "decision_required",
            "reason": "insufficient_information",
            "autonomy": "propose",
            "candidate": chosen,
            "note": "La pieza está en la biblioteca, pero un requisito crítico quedó UNKNOWN. No lo des por cumplido.",
        }
    memory.accepted.add(chosen["lib_id"])
    return {
        "ok": True,
        "decision": "selected",
        "autonomy": "automatic",
        "classification": "DIRECT_EQUIVALENT",
        "candidate": chosen,
        "stage": stage,
    }


def _evaluate(gateway, match: dict, requested: str, hard: dict, required_pins: list[str], architectural: bool) -> dict:
    lib_id = str(match.get("lib_id") or "")
    described = gateway.describe_part(lib_id)
    part = described.get("part") if described.get("ok") else None
    text = ""
    pins: list[dict] = []
    footprint = ""
    if isinstance(part, dict):
        text = f"{part.get('description') or ''} {part.get('value') or ''}"
        pins = list(part.get("pins") or [])
        footprint = str(part.get("footprint") or "")
    checks = {
        "symbol": "PASS" if part else "FAIL",
        "footprint": _footprint_check(gateway, part, footprint),
        "pins": _pin_check(pins, required_pins),
    }
    for key in _ELECTRICAL:
        checks[key] = _electrical_check(text, hard.get(key))
    failed = [name for name, state in checks.items() if state == "FAIL"]
    if architectural:
        classification = "ARCHITECTURAL_ALTERNATIVE"
        result = "CONDITIONAL"
    elif failed:
        classification = "NOT_COMPATIBLE"
        result = "REJECTED"
    elif _is_exact(lib_id, requested) and requested:
        classification = "DIRECT_EQUIVALENT"
        result = "PASS"
    else:
        classification = "UNVERIFIED"
        result = "CONDITIONAL"
    return {
        "lib_id": lib_id,
        "classification": classification,
        "checks": checks,
        "result": result,
        "pin_mapping_changed": checks["pins"] == "FAIL",
    }


def _footprint_check(gateway, part, footprint: str) -> str:
    if part is None:
        return "FAIL"
    if not footprint:
        return "UNKNOWN"
    if isinstance(part, dict) and part.get("footprint_detail"):
        return "PASS"
    try:
        detail = gateway.describe_footprint(footprint)
    except Exception:
        return "UNKNOWN"
    if detail.get("ok"):
        return "PASS"
    return "FAIL"


def _pin_check(pins: list[dict], required_pins: list[str]) -> str:
    if not required_pins:
        return "UNKNOWN"
    known = set()
    for pin in pins:
        known.add(str(pin.get("number") or "").casefold())
        known.add(str(pin.get("name") or "").casefold())
    missing = [pin for pin in required_pins if pin.casefold() not in known]
    return "FAIL" if missing else "PASS"


def _electrical_check(text: str, constraint) -> str:
    if constraint in (None, ""):
        return "UNKNOWN"
    token = str(constraint).strip()
    if not token:
        return "UNKNOWN"
    if token.casefold() in text.casefold():
        return "PASS"
    return "UNKNOWN"


def _unknown_hard(candidate: dict, hard: dict, required_pins: list[str]) -> bool:
    checks = candidate["checks"]
    if checks["footprint"] == "UNKNOWN" or checks["symbol"] != "PASS":
        return True
    if required_pins and checks["pins"] == "UNKNOWN":
        return True
    for key in _ELECTRICAL:
        if hard.get(key) not in (None, "") and checks[key] == "UNKNOWN":
            return True
    return False


def _accept_substitution(memory: DesignMemory, requested: str, lib_id: str) -> None:
    memory.accepted.add(lib_id)
    if requested:
        memory.substitutions[requested] = lib_id


def _change_set(requested: str, chosen: dict, stage: str) -> dict:
    return {
        "agent": "component_selection",
        "reason": "requested_component_unavailable" if requested else "selected_from_function",
        "original": requested,
        "replacement": chosen["lib_id"],
        "classification": chosen["classification"],
        "affected_stages": [stage] if stage else [],
        "requires_revalidation": True,
        "pin_mapping_changed": chosen["pin_mapping_changed"],
    }
