"""Guardián de la intención del usuario. No diseña: registra, compara y bloquea.

El modelo llama a `commit_intent` con lo que pidió el usuario. Ese contrato
vive en la sesión (`Session.memory`) y lo consulta `guard_place` antes de cada
escritura del esquemático. Flujo completo en `app/doc/agents.md`.

- Cada `commit_intent` crea una versión nueva; la anterior no se edita.
- Quitar un componente obligatorio exige que el usuario lo autorice
  (`confirm_removed`). Si no, la respuesta es CONTRADICTS_REQUIREMENT.
- `guard_place` no deja escribir sin contrato, con símbolos que no pasaron por
  `select_component`, con una huella distinta de la verificada, sin un
  componente obligatorio o con uno prohibido.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

# La memoria activa del turno. run_turn la fija para que las herramientas del
# registro (que solo reciben gateway y args) lean la de la sesión correcta.
_active: ContextVar[DesignMemory | None] = ContextVar("kicad_ia_design_memory", default=None)


def activate(memory: DesignMemory) -> Token:
    return _active.set(memory)


def reset(token: Token) -> None:
    _active.reset(token)


def current_memory(gateway) -> DesignMemory:
    """Memoria del turno; fuera de un turno (MCP), una por gateway."""
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
    """Estado de diseño de una sesión de chat.

    contract: última versión del contrato (None hasta el primer commit).
    history: versiones anteriores, sin tocar.
    accepted: lib_id → huella verificada por select_component ("" = símbolo
              de alimentación, no lleva huella).
    substitutions: número pedido → lib_id que el usuario aceptó en su lugar.
    """

    contract: IntentContract | None = None
    history: list[IntentContract] = field(default_factory=list)
    accepted: dict[str, str] = field(default_factory=dict)
    substitutions: dict[str, str] = field(default_factory=dict)

    def commit(self, payload: dict) -> dict:
        goal = str(payload.get("goal") or "").strip()
        if not goal:
            return {"ok": False, "error": "Falta goal: qué quiere construir el usuario, en una frase."}
        required = _strings(payload.get("required_components"))
        if self.contract is not None:
            confirmed = {item.casefold() for item in _strings(payload.get("confirm_removed"))}
            kept = {row.casefold() for row in required}
            dropped = [
                item
                for item in self.contract.required_components
                if item.casefold() not in kept and item.casefold() not in confirmed
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
            self.history.append(self.contract)
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


def _blocked(intent: str, error: str, **extra) -> dict:
    return {"ok": False, "written": False, "intent": intent, "error": error, **extra}


def guard_place(memory: DesignMemory, symbols: list[dict]) -> dict | None:
    """None si se puede escribir. Si no, la respuesta que verá el modelo.

    Si un símbolo llega sin huella, se rellena con la verificada: así el
    esquemático nunca queda con la huella vacía de la biblioteca.
    """
    if memory.contract is None:
        return _blocked("missing", "Falta el contrato de intención. Llama a commit_intent antes de escribir el circuito.")

    # 1. Cada símbolo pasó por select_component.
    missing = sorted({str(s.get("lib_id") or "") for s in symbols if str(s.get("lib_id") or "") not in memory.accepted})
    if missing:
        return _blocked(
            "needs_selection",
            "Estas piezas no pasaron por select_component: " + ", ".join(missing) + ".",
            needs_selection=missing,
        )

    # 2. La huella escrita es la verificada.
    mismatched = []
    for symbol in symbols:
        lib_id = str(symbol.get("lib_id") or "")
        verified = memory.accepted[lib_id]
        written = str(symbol.get("footprint") or "")
        if not verified:
            continue
        if not written:
            symbol["footprint"] = verified
        elif written != verified:
            mismatched.append(f"{symbol.get('reference')}: {written} (verificada {verified})")
    if mismatched:
        return _blocked(
            "footprint_unverified",
            "Huella distinta de la verificada: " + "; ".join(mismatched)
            + ". Pásala por select_component con footprint antes de escribir.",
        )

    # 3. Ningún componente obligatorio falta y ninguno prohibido entra.
    blob = " ".join(f"{s.get('lib_id') or ''} {s.get('value') or ''}" for s in symbols).casefold()
    substituted = {key.casefold() for key in memory.substitutions}
    contradicted = [
        item
        for item in memory.contract.required_components
        if item.casefold() not in blob and item.casefold() not in substituted
    ]
    if contradicted:
        return _blocked(
            "CONTRADICTS_REQUIREMENT",
            "El circuito no incluye lo que el usuario pidió: " + ", ".join(contradicted) + ". No lo sustituyas en silencio.",
        )
    forbidden = [item for item in memory.contract.forbidden_components if item.casefold() in blob]
    if forbidden:
        return _blocked("CONTRADICTS_REQUIREMENT", "El circuito incluye algo que el usuario prohibió: " + ", ".join(forbidden) + ".")
    return None
