"""Contrato de intención del usuario. No diseña: registra, compara y bloquea.

La versión anterior no se reescribe. Quitar un componente obligatorio exige
que el usuario lo haya autorizado en confirm_removed.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

_active: ContextVar[DesignMemory | None] = ContextVar("kicad_ia_design_memory", default=None)


def activate(memory: DesignMemory) -> Token:
    return _active.set(memory)


def reset(token: Token) -> None:
    _active.reset(token)


def current_memory(gateway) -> DesignMemory:
    memory = _active.get()
    if memory is not None:
        return memory
    memory = getattr(gateway, "design_memory", None)
    if memory is None:
        memory = DesignMemory()
        setattr(gateway, "design_memory", memory)
    return memory


@dataclass
class IntentContract:
    version: int
    goal: str
    required_functions: list[str]
    required_components: list[str]
    forbidden_components: list[str]
    preferred: list[str]
    constraints: list[str]
    assumptions: list[str]
    unknowns: list[str]
    acceptance: list[str]

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "goal": self.goal,
            "required_functions": list(self.required_functions),
            "required_components": list(self.required_components),
            "forbidden_components": list(self.forbidden_components),
            "preferred": list(self.preferred),
            "constraints": list(self.constraints),
            "assumptions": list(self.assumptions),
            "unknowns": list(self.unknowns),
            "acceptance": list(self.acceptance),
        }


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass
class DesignMemory:
    contract: IntentContract | None = None
    accepted: set[str] = field(default_factory=set)
    substitutions: dict[str, str] = field(default_factory=dict)

    def commit(self, payload: dict) -> dict:
        goal = str(payload.get("goal") or "").strip()
        if not goal:
            return {"ok": False, "error": "Falta goal: qué quiere construir el usuario, en una frase."}
        required = _strings(payload.get("required_components"))
        if self.contract is not None:
            confirmed = {item.casefold() for item in _strings(payload.get("confirm_removed"))}
            dropped = [
                item
                for item in self.contract.required_components
                if item.casefold() not in {row.casefold() for row in required}
                and item.casefold() not in confirmed
            ]
            if dropped:
                return {
                    "ok": False,
                    "intent": "CONTRADICTS_REQUIREMENT",
                    "error": (
                        "No puedes quitar del contrato: "
                        + ", ".join(dropped)
                        + ". Si el usuario lo autorizó, repítelo en confirm_removed."
                    ),
                }
        version = 1 if self.contract is None else self.contract.version + 1
        self.contract = IntentContract(
            version=version,
            goal=goal,
            required_functions=_strings(payload.get("required_functions")),
            required_components=required,
            forbidden_components=_strings(payload.get("forbidden_components")),
            preferred=_strings(payload.get("preferred")),
            constraints=_strings(payload.get("constraints")),
            assumptions=_strings(payload.get("assumptions")),
            unknowns=_strings(payload.get("unknowns")),
            acceptance=_strings(payload.get("acceptance")),
        )
        return {"ok": True, "intent": "committed", "contract": self.contract.as_dict()}


def guard_place(memory: DesignMemory, symbols: list[dict]) -> dict | None:
    if memory.contract is None:
        return {
            "ok": False,
            "written": False,
            "intent": "missing",
            "error": "Falta el contrato de intención. Llama a commit_intent antes de escribir el circuito.",
        }
    missing = []
    for symbol in symbols:
        lib_id = str(symbol.get("lib_id") or "")
        if lib_id and lib_id not in memory.accepted:
            missing.append(lib_id)
    if missing:
        return {
            "ok": False,
            "written": False,
            "intent": "needs_selection",
            "needs_selection": missing,
            "error": "Estas piezas no pasaron por select_component: " + ", ".join(missing) + ".",
        }
    blob = " ".join(
        f"{symbol.get('lib_id') or ''} {symbol.get('value') or ''}" for symbol in symbols
    ).casefold()
    contradicted = []
    for required in memory.contract.required_components:
        token = required.casefold()
        if token in blob or token in {key.casefold() for key in memory.substitutions}:
            continue
        contradicted.append(required)
    if contradicted:
        return {
            "ok": False,
            "written": False,
            "intent": "CONTRADICTS_REQUIREMENT",
            "error": (
                "El circuito no incluye lo que el usuario pidió: "
                + ", ".join(contradicted)
                + ". No lo sustituyas en silencio."
            ),
        }
    forbidden = [
        item
        for item in memory.contract.forbidden_components
        if item.casefold() in blob
    ]
    if forbidden:
        return {
            "ok": False,
            "written": False,
            "intent": "CONTRADICTS_REQUIREMENT",
            "error": "El circuito incluye algo que el usuario prohibió: " + ", ".join(forbidden) + ".",
        }
    return None
