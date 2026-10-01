"""Herramientas que el modelo (chat) y el servidor MCP pueden llamar.

Cada herramienta:
- tiene esquema JSON (estilo OpenAI function calling),
- delega en un `Gateway`,
- devuelve un dict (`ok` / `error` / datos); nunca lanza al bucle del chat.

Al añadir una: registro aquí + `KipyGateway` + `FakeGateway`. Ver `app/AGENTS.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kicad_ia.kicad.gateway import Gateway

Handler = Callable[[Gateway, dict], dict]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Handler


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def openai_tools(self, exclude: set[str] | None = None) -> list[dict]:
        blocked = exclude or set()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
            if tool.name not in blocked
        ]

    def names(self, exclude: set[str] | None = None) -> list[str]:
        blocked = exclude or set()
        return sorted(name for name in self._tools if name not in blocked)

    def call(self, name: str, arguments: dict | None, gateway: Gateway, exclude: set[str] | None = None) -> dict:
        if exclude and name in exclude:
            return {
                "ok": False,
                "error": (
                    f"La herramienta {name} está desactivada en Ajustes. "
                    "Activa el autoruteo e indica las reglas de fabricación."
                    if name == "autoroute_board"
                    else f"La herramienta {name} no está disponible ahora."
                ),
            }
        tool = self._tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Herramienta desconocida: {name}"}
        try:
            return tool.handler(gateway, arguments or {})
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def _object(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _inspect(gateway: Gateway, _args: dict) -> dict:
    return gateway.inspect()


def _search(gateway: Gateway, args: dict) -> dict:
    kind = str(args.get("kind") or "")
    query = str(args.get("query") or "")
    limit = int(args.get("limit") or 20)
    return gateway.search_parts(kind, query, limit)


def _search_lcsc(gateway: Gateway, args: dict) -> dict:
    query = str(args.get("query") or "")
    if not query:
        return {"ok": False, "error": "Falta query, el nombre o el modelo de la pieza."}
    return gateway.search_lcsc(query, int(args.get("limit") or 8))


def _import_lcsc(gateway: Gateway, args: dict) -> dict:
    lcsc_id = str(args.get("lcsc_id") or "")
    if not lcsc_id:
        return {"ok": False, "error": "Falta lcsc_id, por ejemplo C2040."}
    return gateway.import_lcsc(lcsc_id)


def _describe(gateway: Gateway, args: dict) -> dict:
    lib_id = str(args.get("lib_id") or "")
    if not lib_id:
        return {"ok": False, "error": "Falta lib_id, por ejemplo Device:R."}
    return gateway.describe_part(lib_id)


def _place(gateway: Gateway, args: dict) -> dict:
    symbols = args.get("symbols") or []
    if not isinstance(symbols, list) or not symbols:
        return {"ok": False, "error": "Hace falta al menos un símbolo."}
    for spec in symbols:
        if not isinstance(spec, dict) or not spec.get("lib_id") or not spec.get("reference"):
            return {"ok": False, "error": "Cada símbolo necesita lib_id y reference."}
    return gateway.place_circuit(
        symbols=symbols,
        nets=list(args.get("nets") or []),
        connections=list(args.get("connections") or []),
        replace=bool(args.get("replace")),
    )


def _describe_footprint(gateway: Gateway, args: dict) -> dict:
    lib_id = str(args.get("lib_id") or "")
    if not lib_id:
        return {"ok": False, "error": "Falta lib_id de la huella, por ejemplo Resistor_SMD:R_0603_1608Metric."}
    return gateway.describe_footprint(lib_id)


def _assign(gateway: Gateway, args: dict) -> dict:
    reference = str(args.get("reference") or "")
    footprint = str(args.get("footprint") or "")
    if not reference or not footprint:
        return {"ok": False, "error": "Hacen falta reference y footprint."}
    return gateway.assign_footprint(reference, footprint)


def _sync(gateway: Gateway, _args: dict) -> dict:
    return gateway.sync_board()


def _board(gateway: Gateway, _args: dict) -> dict:
    return gateway.board_state()


def _move(gateway: Gateway, args: dict) -> dict:
    placements = args.get("placements") or []
    if not isinstance(placements, list) or not placements:
        return {"ok": False, "error": "Hace falta placements."}
    return gateway.move_footprints(placements)


def _models(gateway: Gateway, args: dict) -> dict:
    reference = args.get("reference")
    return gateway.list_models(str(reference) if reference else None)


def _routing(gateway: Gateway, args: dict) -> dict:
    mode = str(args.get("mode") or "status")
    action = args.get("action")
    return gateway.routing(mode, str(action) if action else None)


def _render(gateway: Gateway, args: dict) -> dict:
    return gateway.render_view(str(args.get("view") or "schematic"))


def _organize(gateway: Gateway, args: dict) -> dict:
    groups = args.get("groups") or None
    if groups is not None and not isinstance(groups, list):
        return {"ok": False, "error": "groups debe ser una lista de {name, references}."}
    apply = args.get("apply")
    return gateway.organize_layout(str(args.get("target") or "both"), groups, True if apply is None else bool(apply))


def _ipc_place(gateway: Gateway, args: dict) -> dict:
    groups = args.get("groups") or None
    if groups is not None and not isinstance(groups, list):
        return {"ok": False, "error": "groups debe ser una lista de {name, references}."}
    return gateway.ipc_place_components(
        groups,
        apply=bool(args.get("apply")),
        candidate_id=str(args["candidate_id"]) if args.get("candidate_id") else None,
        class_id=str(args.get("class_id") or "2"),
    )


def _autoroute(gateway: Gateway, args: dict) -> dict:
    ignore = args.get("ignore_net_classes")
    if ignore is not None and not isinstance(ignore, list):
        return {"ok": False, "error": "ignore_net_classes debe ser una lista de nombres."}
    return gateway.autoroute_board(
        apply=bool(args.get("apply")),
        candidate_id=str(args["candidate_id"]) if args.get("candidate_id") else None,
        ignore_net_classes=ignore,
        max_passes=int(args.get("max_passes") or 100),
    )


def _ipc_validate(gateway: Gateway, args: dict) -> dict:
    return gateway.ipc_validate_correct(apply=bool(args.get("apply")), class_id=str(args.get("class_id") or "2"))


_SYMBOL = {
    "type": "object",
    "properties": {
        "lib_id": {"type": "string", "description": "Identificador de biblioteca, por ejemplo Device:R."},
        "reference": {"type": "string"},
        "value": {"type": "string"},
        "footprint": {"type": "string"},
        "x_mm": {"type": "number", "description": "Opcional. Sin coordenadas se reparten solos en la hoja."},
        "y_mm": {"type": "number"},
    },
    "required": ["lib_id", "reference"],
}

_NET = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Nombre de la red, por ejemplo +3V3, GND, SPI_SCK."},
        "pins": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "pin": {"type": "string", "description": "Número del pin o su nombre, tal como sale en describe_part."},
                },
                "required": ["reference", "pin"],
            },
        },
    },
    "required": ["name", "pins"],
}

_CONNECTION = {
    "type": "object",
    "properties": {
        "from_reference": {"type": "string"},
        "from_pin": {"type": "string"},
        "to_reference": {"type": "string"},
        "to_pin": {"type": "string"},
    },
    "required": ["from_reference", "from_pin", "to_reference", "to_pin"],
}


def build_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            Tool(
                "inspect_context",
                "Lee el proyecto abierto, la selección actual del editor, el esquemático y la placa. Úsala antes de modificar nada.",
                _object({}, []),
                _inspect,
            ),
            Tool(
                "search_parts",
                "Busca en las bibliotecas de símbolos y huellas configuradas en KiCad (sym-lib-table, fp-lib-table). kind=model devuelve los modelos 3D de las huellas encontradas. No inventes un lib_id: búscalo aquí.",
                _object(
                    {
                        "kind": {"type": "string", "enum": ["symbol", "footprint", "model"]},
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    ["kind", "query"],
                ),
                _search,
            ),
            Tool(
                "search_lcsc",
                "Busca en LCSC/JLCPCB cuando la pieza no está en las bibliotecas de KiCad. Devuelve códigos C. No importa nada: enseña las opciones y espera a que el usuario elija.",
                _object({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
                _search_lcsc,
            ),
            Tool(
                "import_lcsc",
                "Descarga símbolo, huella y modelo 3D de un código LCSC (C seguido de números) a la biblioteca kicad-ia del proyecto. Llámala solo después de que el usuario confirme el código.",
                _object({"lcsc_id": {"type": "string"}}, ["lcsc_id"]),
                _import_lcsc,
            ),
            Tool(
                "describe_part",
                "Lee el símbolo de la biblioteca de KiCad: pines (número, nombre, tipo), huella por defecto y su modelo 3D. Hace falta para conectar.",
                _object({"lib_id": {"type": "string"}}, ["lib_id"]),
                _describe,
            ),
            Tool(
                "describe_footprint",
                "Lee una huella de la biblioteca de KiCad: pads, montaje y modelos 3D con su ruta y si el archivo existe.",
                _object({"lib_id": {"type": "string"}}, ["lib_id"]),
                _describe_footprint,
            ),
            Tool(
                "place_circuit",
                "Escribe el circuito en el esquemático del proyecto. Cada red es una lista de pines; el plugin pone una etiqueta con el nombre de la red en cada pin, así que no hacen falta coordenadas ni cables.",
                _object(
                    {
                        "symbols": {"type": "array", "items": _SYMBOL},
                        "nets": {"type": "array", "items": _NET},
                        "connections": {
                            "type": "array",
                            "items": _CONNECTION,
                            "description": "Alternativa a nets: pares pin a pin. Mejor usar nets con nombre.",
                        },
                        "replace": {
                            "type": "boolean",
                            "description": "Borra lo que hay en la hoja antes de escribir (queda copia). Úsalo para rehacer un diseño que ya escribiste en esta conversación, o si el usuario lo pide.",
                        },
                    },
                    ["symbols", "nets"],
                ),
                _place,
            ),
            Tool(
                "assign_footprint",
                "Cambia la huella de un símbolo ya colocado en el esquemático. La huella debe existir en las bibliotecas de KiCad.",
                _object(
                    {"reference": {"type": "string"}, "footprint": {"type": "string"}},
                    ["reference", "footprint"],
                ),
                _assign,
            ),
            Tool(
                "sync_board",
                "Valida el esquemático con ERC y el netlist de kicad-cli. No importa la placa: devuelve el paso F8 que hace el usuario en el editor de PCB.",
                _object({}, []),
                _sync,
            ),
            Tool(
                "board_state",
                "Resume huellas, pistas, vías y zonas de la placa.",
                _object({}, []),
                _board,
            ),
            Tool(
                "move_footprints",
                "Mueve huellas ya presentes en la placa a coordenadas en milímetros.",
                _object(
                    {
                        "placements": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "reference": {"type": "string"},
                                    "x_mm": {"type": "number"},
                                    "y_mm": {"type": "number"},
                                },
                                "required": ["reference", "x_mm", "y_mm"],
                            },
                        }
                    },
                    ["placements"],
                ),
                _move,
            ),
            Tool(
                "list_models",
                "Lista los modelos 3D de una referencia, de la selección o de las huellas de la placa.",
                _object({"reference": {"type": "string"}}, []),
                _models,
            ),
            Tool(
                "routing",
                "Estado del cobre o arranque explícito de una acción del router de KiCad. mode=status no modifica la placa. mode=external explica cómo exportar Specctra DSN a mano.",
                _object(
                    {
                        "mode": {"type": "string", "enum": ["status", "interactive", "external"]},
                        "action": {
                            "type": "string",
                            "description": "Nombre TOOL_ACTION de KiCad. Solo para mode=interactive. Es una API inestable.",
                        },
                    },
                    ["mode"],
                ),
                _routing,
            ),
            Tool(
                "render_view",
                "Genera una imagen del circuito para enseñarla en el chat: schematic (hoja guardada), pcb (capas de cobre y serigrafía), pcb_3d, pcb_3d_bottom o pcb_3d_iso. Devuelve image; el chat la muestra sola, no copies la URL.",
                _object({"view": {"type": "string", "enum": ["schematic", "pcb", "pcb_3d", "pcb_3d_bottom", "pcb_3d_iso"]}}, ["view"]),
                _render,
            ),
            Tool(
                "organize_layout",
                "Reordena el circuito en bloques por función (alimentación, microcontrolador, pantalla...). En el esquemático rehace la hoja con un marco por grupo; en la placa mueve las huellas por grupos dentro del contorno. Sin groups agrupa solo cada pasivo con el integrado al que sirve.",
                _object(
                    {
                        "target": {"type": "string", "enum": ["schematic", "pcb", "both"]},
                        "groups": {
                            "type": "array",
                            "description": "Opcional. Grupos con nombre funcional y sus referencias. Las que falten van a «Otros».",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "references": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["name", "references"],
                            },
                        },
                        "apply": {"type": "boolean", "description": "false calcula el plan sin tocar nada. Por defecto true."},
                    },
                    ["target"],
                ),
                _organize,
            ),
            Tool(
                "ipc_place_components",
                "Coloca huellas en la PCB según pre-chequeo IPC Clase 2 (holguras, borde, desacoplos, conectores). "
                "Por defecto apply=false: devuelve placements, ipc_findings, candidate_id e imagen. "
                "Solo aplica con apply=true y el candidate_id que devolvió la vista previa, tras confirmar con el usuario. "
                "No mueve huellas bloqueadas. Si hay pistas, avisa que quedarán desfasadas.",
                _object(
                    {
                        "groups": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "references": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["name", "references"],
                            },
                        },
                        "apply": {"type": "boolean"},
                        "candidate_id": {"type": "string"},
                        "class_id": {"type": "string", "description": "Clase IPC; por defecto 2."},
                    },
                    [],
                ),
                _ipc_place,
            ),
            Tool(
                "autoroute_board",
                "Autorutea la placa con FreeRouting (DSN/SES vía pcbnew). Siempre calcula primero un candidato: "
                "exporta DSN, rutea, importa SES en una copia, pasa DRC y compara con el baseline. "
                "Devuelve candidate_id, imágenes before/after, drc y score. "
                "NO apliques cobre hasta que el usuario confirme y entonces apply=true con ese candidate_id. "
                "El revisor de PCB valida el informe.",
                _object(
                    {
                        "apply": {"type": "boolean"},
                        "candidate_id": {"type": "string"},
                        "ignore_net_classes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Clases de red que FreeRouting no debe tocar, p. ej. GND si ya hay plano.",
                        },
                        "max_passes": {"type": "integer"},
                    },
                    [],
                ),
                _autoroute,
            ),
            Tool(
                "ipc_validate_correct",
                "Audita la PCB con DRC de KiCad y reglas IPC Clase 2. "
                "Con apply=false solo informa. Con apply=true aplica únicamente correcciones seguras de colocación "
                "(separar solapes leves, empujar del borde, acercar desacoplos); el resto queda en recommendations. "
                "No es una certificación IPC.",
                _object(
                    {
                        "apply": {"type": "boolean"},
                        "class_id": {"type": "string"},
                    },
                    [],
                ),
                _ipc_validate,
            ),
        ]
    )
