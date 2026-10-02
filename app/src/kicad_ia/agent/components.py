"""Servicio de selección de componentes. Decide QUÉ símbolo y QUÉ huella.

Lo llama el modelo con `select_component` en cualquier fase: antes de escribir
el esquemático y también desde la placa, si una huella no cabe o falla el DRC.
Flujo completo en `app/doc/agents.md`.

Reglas que este módulo no rompe:

- Solo usa lo que devuelven las bibliotecas de KiCad (`search_parts`,
  `describe_part`, `describe_footprint`). No inventa lib_id, pines ni huellas.
- Un dato que no se pudo leer queda en UNKNOWN. Nunca pasa a PASS por inferencia.
- Un componente sin huella verificada no se acepta. La única excepción son los
  símbolos de alimentación (power:GND, +3V3): no van a la placa.
- Con varias opciones, pin que no encaja o dato crítico en UNKNOWN, la salida
  es `decision_required` o `request_user`: decide el usuario.
- Un sustituto solo se acepta con `allow_substitution` (el usuario ya lo
  aceptó), un único candidato y sin cambio de arquitectura.

Lo aceptado se guarda en `DesignMemory.accepted` (lib_id → huella). El guardia
de `place_circuit` solo deja escribir símbolos que están ahí.
"""

from __future__ import annotations

import fnmatch

from kicad_ia.agent.intent import DesignMemory

# Restricciones eléctricas que el usuario puede fijar en `hard`. Se comparan
# con el texto de la biblioteca (descripción y valor); sin datasheet, lo que
# no aparezca literal queda en UNKNOWN.
_ELECTRICAL = ("voltage", "current", "power", "temperature", "tolerance", "frequency")

# Estados de la comprobación de huella.
FP_PASS = "PASS"  # existe en fp-lib-table y tiene pads para todos los pines
FP_FAIL = "FAIL"  # nombrada pero no está, o le faltan pads
FP_MISSING = "MISSING"  # el símbolo no trae huella y nadie la eligió
FP_NOT_REQUIRED = "NOT_REQUIRED"  # símbolo de alimentación, no va a la placa

MAX_FOOTPRINT_CANDIDATES = 8


def select_component(gateway, args: dict, memory: DesignMemory) -> dict:
    """Punto de entrada de la herramienta. Devuelve siempre `decision`:

    - `selected`: aceptado; queda en memory.accepted con su huella.
    - `footprint_required`: el símbolo sirve, pero falta elegir huella.
    - `decision_required`: hay opciones y debe elegir el usuario.
    - `request_user`: no hay nada válido o falta información.
    """
    requested = str(args.get("requested_part") or "").strip()
    function = str(args.get("function") or "").strip()
    stage = str(args.get("stage") or "").strip()
    queries = [str(item).strip() for item in (args.get("queries") or []) if str(item).strip()]
    hard = args.get("hard") if isinstance(args.get("hard"), dict) else {}
    required_pins = [str(pin) for pin in (args.get("required_pins") or [])]
    footprint = str(args.get("footprint") or "").strip()
    architectural = bool(args.get("architectural_change"))
    if not requested and not function and not queries:
        return {"ok": False, "error": "Indica requested_part, function o queries. No inventes un lib_id."}

    # 1. Búsqueda exacta del número pedido.
    exact = _search_exact(gateway, requested) if requested else []
    if exact:
        return _decide_exact(gateway, memory, exact, requested, hard, required_pins, footprint, stage, architectural)

    # 2. No está. Sin función declarada no hay base para buscar sustitutos:
    #    deducirla del número de parte sería inventar.
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

    # 3. Candidatos por función, no por nombre.
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

    # 4. Evaluar cada candidato contra las restricciones duras.
    candidates = [
        _evaluate(gateway, match, requested, hard, required_pins, footprint, architectural)
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

    # 5. Autonomía: solo un candidato, aceptado por el usuario, sin cambio de
    #    arquitectura y sin ningún dato crítico en UNKNOWN.
    if len(viable) == 1 and args.get("allow_substitution") and not architectural:
        chosen = viable[0]
        if chosen["checks"]["footprint"] == FP_MISSING:
            return _footprint_required(chosen, stage)
        if not _unknown_hard(chosen, hard, required_pins):
            _accept(memory, chosen, requested)
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
    """Exacto = lib_id completo o nombre del símbolo igual, sin mayúsculas."""
    want = requested.casefold().strip()
    name = lib_id.split(":")[-1].casefold()
    return lib_id.casefold() == want or name == want


def _decide_exact(gateway, memory, matches, requested, hard, required_pins, footprint, stage, architectural) -> dict:
    # El mismo nombre en dos bibliotecas puede tener otro pinout o encapsulado.
    if len(matches) > 1:
        candidates = [
            _evaluate(gateway, match, requested, hard, required_pins, footprint, architectural) for match in matches
        ]
        return {
            "ok": True,
            "decision": "decision_required",
            "reason": "multiple_valid_alternatives",
            "autonomy": "propose",
            "requested": requested,
            "candidates": candidates,
        }
    chosen = _evaluate(gateway, matches[0], requested, hard, required_pins, footprint, architectural)
    if chosen["result"] == "REJECTED" or architectural:
        return {
            "ok": True,
            "decision": "request_user",
            "reason": "critical_constraint_conflict" if chosen["result"] == "REJECTED" else "architectural_change",
            "candidate": chosen,
            "stage": stage,
            "note": "No lo uses. El dato comprobado no cumple, o el cambio de arquitectura no puede ser silencioso.",
        }
    if chosen["checks"]["footprint"] == FP_MISSING:
        return _footprint_required(chosen, stage)
    if _unknown_hard(chosen, hard, required_pins):
        return {
            "ok": True,
            "decision": "decision_required",
            "reason": "insufficient_information",
            "autonomy": "propose",
            "candidate": chosen,
            "note": "La pieza está en la biblioteca, pero un requisito crítico quedó UNKNOWN. No lo des por cumplido.",
        }
    _accept(memory, chosen, "")
    return {
        "ok": True,
        "decision": "selected",
        "autonomy": "automatic",
        "classification": "DIRECT_EQUIVALENT",
        "candidate": chosen,
        "footprint": chosen["footprint"],
        "stage": stage,
    }


def _footprint_required(chosen: dict, stage: str) -> dict:
    """El símbolo vale, pero sin huella no puede pasar a la placa."""
    options = chosen.get("footprint_candidates") or []
    note = (
        "El símbolo no trae huella. Elige una de footprint_candidates y vuelve a llamar con footprint. "
        "Si el usuario no dijo el encapsulado (0603, 0805, THT…), pregúntale."
        if options
        else "El símbolo no trae huella y no encontré candidatas. Busca con search_parts kind=footprint por encapsulado "
        "y vuelve a llamar con footprint, o pregunta al usuario."
    )
    return {
        "ok": True,
        "decision": "footprint_required",
        "reason": "footprint_missing",
        "candidate": chosen,
        "footprint_candidates": options,
        "stage": stage,
        "note": note,
    }


def _evaluate(
    gateway, match: dict, requested: str, hard: dict, required_pins: list[str], footprint: str, architectural: bool
) -> dict:
    """Comprueba un candidato. Cada check vale PASS, FAIL, UNKNOWN (o los estados FP_*)."""
    lib_id = str(match.get("lib_id") or "")
    described = gateway.describe_part(lib_id)
    part = described.get("part") if described.get("ok") else None
    text = ""
    pins: list[dict] = []
    if isinstance(part, dict):
        text = f"{part.get('description') or ''} {part.get('value') or ''}"
        pins = list(part.get("pins") or [])
    fp = _footprint_check(gateway, lib_id, part, pins, footprint)
    checks = {
        "symbol": "PASS" if part else "FAIL",
        "footprint": fp["state"],
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
        # Sin datasheet no podemos afirmar FUNCTIONAL ni DIRECT_EQUIVALENT.
        classification = "UNVERIFIED"
        result = "CONDITIONAL"
    row = {
        "lib_id": lib_id,
        "classification": classification,
        "checks": checks,
        "result": result,
        "footprint": fp["footprint"],
        "footprint_source": fp["source"],
        "pin_mapping_changed": checks["pins"] == "FAIL",
    }
    if fp.get("detail"):
        row["footprint_detail"] = fp["detail"]
    if fp.get("candidates"):
        row["footprint_candidates"] = fp["candidates"]
    return row


def _footprint_check(gateway, lib_id: str, part, pins: list[dict], requested_fp: str) -> dict:
    """¿Este símbolo tiene una huella real en las bibliotecas de huellas?

    Orden: la huella que pidió el modelo/usuario, si no la del símbolo. Si no
    hay ninguna, busca candidatas con los filtros ki_fp_filters del símbolo y
    devuelve MISSING: alguien tiene que elegir. Una huella con menos pads que
    números de pin distintos no puede llevar el pinout: FAIL.
    """
    if part is None:
        return {"state": FP_FAIL, "footprint": "", "source": ""}
    if _is_power(lib_id, part):
        return {"state": FP_NOT_REQUIRED, "footprint": "", "source": "power_symbol"}
    footprint = requested_fp or str(part.get("footprint") or "")
    source = "requested" if requested_fp else "symbol_default"
    numbers = {str(pin.get("number") or "") for pin in pins if str(pin.get("number") or "")}
    if not footprint:
        return {
            "state": FP_MISSING,
            "footprint": "",
            "source": "",
            "candidates": _footprint_candidates(gateway, part, len(numbers)),
        }
    try:
        described = gateway.describe_footprint(footprint)
    except Exception:
        described = {"ok": False}
    if not described.get("ok"):
        return {"state": FP_FAIL, "footprint": footprint, "source": source, "detail": {"error": "no está en las bibliotecas de huellas"}}
    detail = described.get("footprint") or {}
    pads = int(detail.get("pad_count") or 0)
    summary = {"pad_count": pads, "pin_count": len(numbers), "mounting": detail.get("mounting", "")}
    if pads and numbers and pads < len(numbers):
        summary["error"] = f"la huella tiene {pads} pads y el símbolo {len(numbers)} pines"
        return {"state": FP_FAIL, "footprint": footprint, "source": source, "detail": summary}
    return {"state": FP_PASS, "footprint": footprint, "source": source, "detail": summary}


def _is_power(lib_id: str, part: dict) -> bool:
    return bool(part.get("power_symbol")) or lib_id.startswith("power:")


def _footprint_candidates(gateway, part: dict, pin_count: int) -> list[str]:
    """Huellas reales que cumplen los filtros del símbolo (R_*, SOT?23*).

    Solo devuelve lib_id que la búsqueda encontró, cuyo nombre encaja con algún
    filtro y cuyo número de pads coincide con los pines del símbolo. Así una
    resistencia de 2 pines no recibe una red de 8. No completa nombres a mano.
    """
    filters = [str(item) for item in (part.get("footprint_filters") or []) if str(item)]
    found: list[str] = []
    for pattern in filters:
        query = pattern.replace("*", " ").replace("?", " ").strip()
        if not query:
            continue
        rows = gateway.search_parts("footprint", query, 40).get("matches") or []
        for row in rows:
            fp_id = str(row.get("lib_id") or "")
            name = fp_id.split(":")[-1]
            if not fp_id or fp_id in found or not fnmatch.fnmatch(name.casefold(), pattern.casefold()):
                continue
            if pin_count and _pad_count(gateway, fp_id) != pin_count:
                continue
            found.append(fp_id)
            if len(found) >= MAX_FOOTPRINT_CANDIDATES:
                return found
    return found


def _pad_count(gateway, footprint: str) -> int:
    try:
        described = gateway.describe_footprint(footprint)
    except Exception:
        return 0
    return int((described.get("footprint") or {}).get("pad_count") or 0) if described.get("ok") else 0


def _pin_check(pins: list[dict], required_pins: list[str]) -> str:
    """Los pines que pide la etapa (EN, VIN, 3) existen por número o nombre."""
    if not required_pins:
        return "UNKNOWN"
    known = set()
    for pin in pins:
        known.add(str(pin.get("number") or "").casefold())
        known.add(str(pin.get("name") or "").casefold())
    missing = [pin for pin in required_pins if pin.casefold() not in known]
    return "FAIL" if missing else "PASS"


def _electrical_check(text: str, constraint) -> str:
    """PASS solo si el texto de la biblioteca dice literalmente el valor.

    No hay FAIL eléctrico: la descripción no basta para afirmar que algo no
    cumple. Lo que no aparece queda UNKNOWN y bloquea la autonomía.
    """
    if constraint in (None, ""):
        return "UNKNOWN"
    token = str(constraint).strip()
    if not token:
        return "UNKNOWN"
    if token.casefold() in text.casefold():
        return "PASS"
    return "UNKNOWN"


def _unknown_hard(candidate: dict, hard: dict, required_pins: list[str]) -> bool:
    """¿Queda alguna restricción dura sin verificar? Si sí, no hay autonomía."""
    checks = candidate["checks"]
    if checks["symbol"] != "PASS":
        return True
    if checks["footprint"] not in (FP_PASS, FP_NOT_REQUIRED):
        return True
    if required_pins and checks["pins"] == "UNKNOWN":
        return True
    for key in _ELECTRICAL:
        if hard.get(key) not in (None, "") and checks[key] == "UNKNOWN":
            return True
    return False


def _accept(memory: DesignMemory, chosen: dict, requested: str) -> None:
    """Registra lib_id con la huella verificada ("" = símbolo de alimentación)."""
    memory.accepted[chosen["lib_id"]] = chosen["footprint"]
    if requested:
        memory.substitutions[requested] = chosen["lib_id"]


def _change_set(requested: str, chosen: dict, stage: str) -> dict:
    """Rastro de la sustitución: qué se pidió, qué entra y qué hay que revalidar."""
    return {
        "agent": "component_selection",
        "reason": "requested_component_unavailable" if requested else "selected_from_function",
        "original": requested,
        "replacement": chosen["lib_id"],
        "footprint": chosen["footprint"],
        "classification": chosen["classification"],
        "affected_stages": [stage] if stage else [],
        "requires_revalidation": True,
        "pin_mapping_changed": chosen["pin_mapping_changed"],
    }
