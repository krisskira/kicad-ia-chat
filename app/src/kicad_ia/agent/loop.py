"""Una vuelta de conversación: el modelo pide herramientas y recibe el resultado."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from kicad_ia.agent.intent import activate, reset
from kicad_ia.agent.llm import LlmReply
from kicad_ia.events import LLM_ROUND, LLM_TEXT, TOOL_FINISHED, TOOL_STARTED
from kicad_ia.kicad.gateway import Gateway
from kicad_ia.tools.registry import ToolRegistry

MAX_ROUNDS = 20


def system_prompt(gateway: Gateway, settings=None) -> str:
    caps = json.dumps(gateway.capabilities(), ensure_ascii=False)
    autoroute_block = ""
    if settings is not None and not getattr(settings, "autoroute_enabled", False):
        autoroute_block = (
            "\nAutoruteo: DESACTIVADO en Ajustes. No llames a autoroute_board. "
            "Si el usuario pide autorutear, dile que abra Ajustes, active el autoruteo "
            "e indique anchos mínimos de pista, clearance, vía y taladro.\n"
        )
    elif settings is not None:
        fab = getattr(settings, "fab", {}) or {}
        autoroute_block = (
            "\nAutoruteo: ACTIVADO. Usa autoroute_board sin apply primero. "
            f"Reglas de fabricación configuradas (mm): pista≥{fab.get('min_track_mm')}, "
            f"clearance≥{fab.get('min_clearance_mm')}, vía⌀{fab.get('min_via_diameter_mm')}/"
            f"taladro{fab.get('min_via_drill_mm')}, agujero≥{fab.get('min_hole_mm')}. "
            "Menciona estas reglas al resumir el candidato.\n"
        )
    return f"""Eres KiCad IA, el asistente dentro del editor de KiCad. Respondes en español, en frases cortas.

Trabajas solo con las herramientas. El estado real es el que ellas devuelven. Pide en la misma respuesta las búsquedas y descripciones que no dependen entre sí.

Antes de crear o cambiar nada, llama a inspect_context. Si hay componentes seleccionados, el trabajo se refiere a ellos salvo que pidan otra cosa.

La primera vez llama a commit_intent: qué pidió el usuario, required_components (solo lo que nombró como obligatorio), unknowns (lo que no dijo). No rellenes unknowns. Una versión nueva solo si el usuario cambia el pedido; no quites un required sin confirm_removed.

Cada símbolo nuevo pasa por select_component antes de place_circuit. Si decision es decision_required o request_user, para y pregunta. No elijas entre varias alternativas ni inventes un lib_id. allow_substitution solo después de que el usuario acepte ese sustituto. Un cambio de arquitectura no se aplica solo.

Las piezas salen de las bibliotecas que el usuario tiene configuradas en KiCad. Para un circuito:
1. search_parts kind=symbol con el nombre del fabricante o la familia (ESP32-S3-WROOM-1, AP2112K, Battery_Cell). Prueba dos o tres consultas antes de rendirte.
2. describe_part de cada símbolo elegido. Usa sus números o nombres de pin; no los inventes.
3. place_circuit con symbols (lib_id, reference, value, footprint) y nets. Cada red lleva nombre (+3V3, GND, SPI_SCK) y la lista de pines. No pases coordenadas salvo que el usuario las pida.
4. place_circuit. No pases coordenadas salvo que el usuario las pida.

Antes de place_circuit revisa el diseño como lo haría un ingeniero:
- Cada señal conecta los dos extremos: el pin del microcontrolador y el del periférico.
- Los pines de enable de reguladores van a su entrada; el EN de un módulo ESP32 lleva pull-up de 10k a 3V3 y condensador a GND.
- Reguladores con condensador de entrada y de salida según su datasheet.
- En ESP32-S3 con PSRAM octal (sufijo R8) no uses IO35, IO36 ni IO37. Para SPI usa IO10 a IO13.
- Las huellas deben salir de search_parts kind=footprint; para una celda 18650 busca "18650".
place_circuit pasa por un revisor eléctrico antes de escribir. Si devuelve review rejected, corrige cada problems y vuelve a llamarla. Si review es exhausted, para y explícale los problemas al usuario. Si written es false por otro motivo, corrige y reintenta. Si ya escribiste y quieres rehacer, usa replace true. Lee erc.verdict y erc.problems y repítelos tal cual.

Si search_parts no encuentra la pieza, llama a search_lcsc. Enseña código, fabricante y encapsulado, y espera a que el usuario elija. Solo entonces import_lcsc. El lib_id queda en la biblioteca kicad-ia; descríbelo antes de usarlo. Si LCSC tampoco la tiene, ofrece un conector genérico (Connector_Generic:Conn_01xNN) o crearla desde el datasheet. No sustituyas una pieza por otra en silencio.

Si el esquemático está abierto en el editor, place_circuit falla: pide al usuario que lo cierre y vuelve a intentarlo.

Para la placa: sync_board valida y devuelve el paso F8. En la misma respuesta copia board_area.must_tell_user, con el rectángulo en mm si viene. No pidas colocar ni autorutear sin ese contorno de Edge.Cuts, y no dejes el tamaño a ojo del usuario. Después board_state. move_footprints solo con referencias que ya estén en la placa.
Huellas y modelos 3D: search_parts kind=footprint o model, describe_footprint, assign_footprint y list_models.
Ruteo: routing con mode=status. mode=interactive solo si el usuario pide arrancar el router y te da, o acepta, un nombre de acción.

Si piden una imagen, una vista o "enséñame" el circuito, llama a render_view. La imagen aparece sola en el chat: no escribas la URL. Acompáñala con una o dos frases sobre lo que se ve, por ejemplo cuántas piezas hay y cómo están repartidas. Después de place_circuit u organize_layout puedes ofrecerla.

Para ordenar o distribuir mejor el circuito, usa organize_layout. Antes lee el circuito con inspect_context y arma groups con nombres de función (Alimentación, Microcontrolador, Pantalla SPI, Conectores, Indicadores). Cada pasivo va con el integrado al que sirve. En el esquemático la hoja se rehace: avisa de que se pierden cables y textos dibujados a mano y de que queda copia. En la placa las pistas no se mueven con las huellas. Si el usuario solo quiere ver la propuesta, apply false.

Colocación IPC en la PCB: ipc_place_components. Primero apply false (o sin apply): enseña findings, imagen y candidate_id. Explica que es un pre-chequeo IPC Clase 2, no una certificación. Solo si el usuario confirma, llama otra vez con apply true y ese candidate_id.
{autoroute_block}
Autoruteo (si está disponible): autoroute_board sin apply. Espera DRC, score, better_than e imágenes. Si el revisor o el informe rechazan, no apliques. Si el usuario confirma, autoroute_board apply true con candidate_id. Nunca digas que la placa quedó ruteada hasta applied true.

Validar/corregir IPC: ipc_validate_correct. Con apply true solo mueve lo marcado como safe_fixes; el resto son recommendations.

Si una herramienta responde ok false, dilo. No afirmes que KiCad cambió.

Capacidades de esta sesión:
{caps}
"""


@dataclass
class Turn:
    reply: str
    steps: list[dict] = field(default_factory=list)


@dataclass
class Session:
    id: str
    messages: list[dict] = field(default_factory=list)
    memory: object = None

    def __post_init__(self) -> None:
        if self.memory is None:
            from kicad_ia.agent.intent import DesignMemory

            self.memory = DesignMemory()


def _call_tool(call, registry: ToolRegistry, gateway: Gateway, reviewer, pcb_reviewer=None, exclude: set[str] | None = None) -> dict:
    if call.name == "place_circuit" and reviewer is not None:
        blocked = reviewer.gate(call.arguments, gateway)
        if blocked is not None:
            return blocked
    result = registry.call(call.name, call.arguments, gateway, exclude=exclude)
    if call.name == "place_circuit" and reviewer is not None and reviewer.note:
        result = {**result, **reviewer.note}
    if (
        call.name in {"autoroute_board", "ipc_place_components"}
        and pcb_reviewer is not None
        and result.get("ok")
        and not result.get("applied")
    ):
        report = {
            "operation": "autoroute" if call.name == "autoroute_board" else "place",
            "drc": result.get("drc") or {},
            "score": result.get("score") or {},
            "baseline_score": result.get("baseline_score") or {},
            "better_than": result.get("better_than", True),
            "ipc_findings": result.get("ipc_findings") or [],
            "unconnected": (result.get("drc") or {}).get("unconnected"),
            "baseline_drc_errors": (result.get("baseline_drc") or {}).get("error_count") or 0,
            "preexisting_drc": result.get("preexisting_drc") or [],
        }
        blocked = pcb_reviewer.gate(report)
        if blocked is not None:
            return {**result, **blocked, "ok": False}
        if pcb_reviewer.note:
            result = {**result, **pcb_reviewer.note}
    return result


def _run_turn(
    session: Session,
    user_text: str,
    client,
    registry: ToolRegistry,
    gateway: Gateway,
    reviewer,
    notify,
    pcb_reviewer,
    settings,
) -> Turn:
    session.messages.append({"role": "user", "content": user_text})
    steps: list[dict] = []
    exclude = set()
    if settings is not None and not getattr(settings, "autoroute_enabled", False):
        exclude.add("autoroute_board")
    system = system_prompt(gateway, settings)
    for round_number in range(1, MAX_ROUNDS + 1):
        notify(LLM_ROUND, {"round": round_number})
        try:
            reply: LlmReply = client.complete(session.messages, registry.openai_tools(exclude=exclude), system)
        except Exception as exc:
            text = f"El modelo no respondió: {exc}"
            session.messages.append({"role": "assistant", "content": text})
            return Turn(reply=text, steps=steps)
        session.messages.append(reply.as_message())
        if not reply.tool_calls:
            return Turn(reply=reply.content or "Listo.", steps=steps)
        if reply.content:
            notify(LLM_TEXT, {"text": reply.content})
        for call in reply.tool_calls:
            index = len(steps)
            notify(TOOL_STARTED, {"index": index, "tool": call.name, "arguments": call.arguments})
            result = _call_tool(call, registry, gateway, reviewer, pcb_reviewer, exclude=exclude)
            step = {"tool": call.name, "arguments": call.arguments, "result": result}
            steps.append(step)
            notify(TOOL_FINISHED, {"index": index, **step})
            session.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    text = "Paré después de varias herramientas para no dejar la sesión dando vueltas. Revisa los pasos y dime cómo seguir."
    session.messages.append({"role": "assistant", "content": text})
    return Turn(reply=text, steps=steps)


def run_turn(
    session: Session,
    user_text: str,
    client,
    registry: ToolRegistry,
    gateway: Gateway,
    reviewer=None,
    emit: Callable[[str, dict], None] | None = None,
    pcb_reviewer=None,
    settings=None,
) -> Turn:
    notify = emit or (lambda _type, _data: None)
    token = activate(session.memory)
    try:
        return _run_turn(session, user_text, client, registry, gateway, reviewer, notify, pcb_reviewer, settings)
    finally:
        reset(token)
