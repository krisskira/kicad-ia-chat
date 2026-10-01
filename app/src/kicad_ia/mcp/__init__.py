"""Servidor MCP (stdio): expone las herramientas de KiCad IA a Cursor y otros clientes.

Arranque:
  python -m kicad_ia.mcp

En Cursor (~/.cursor/mcp.json o .cursor/mcp.json del proyecto):
  {
    "mcpServers": {
      "kicad-ia": {
        "command": "/ruta/app/.venv/bin/python",
        "args": ["-m", "kicad_ia.mcp"],
        "cwd": "/ruta/app",
        "env": { "KICAD_MODE": "auto" }
      }
    }
  }

KiCad debe estar abierto con la API activada. El autoruteo solo aparece si está
habilitado en Ajustes (user-settings.json) o AUTOROUTE_ENABLED=1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from kicad_ia.config import Settings
from kicad_ia.kicad.serialized import SerializedGateway
from kicad_ia.kicad.session import open_gateway
from kicad_ia.tools.registry import ToolRegistry, build_registry

log = logging.getLogger("kicad_ia.mcp")

INSTRUCTIONS = """Eres un cliente MCP de KiCad IA. Las herramientas modifican el proyecto abierto en KiCad.

Reglas:
- Antes de cambiar nada, llama a inspect_context.
- Las piezas salen de search_parts (bibliotecas de KiCad). Si no hay, search_lcsc y espera confirmación antes de import_lcsc.
- place_circuit escribe el esquemático por archivo: el editor de esquemáticos debe estar cerrado.
- En la placa, sync_board solo valida; el usuario hace F8. move_footprints / ipc_place_components / autoroute_board trabajan con apply=false primero y candidate_id.
- autoroute_board solo existe si el usuario activó el autoruteo en Ajustes.
- No afirmes que KiCad cambió si ok es false o el backend es fake.
- Responde al usuario en español.
"""

MAX_RESULT_CHARS = 120_000


def excluded_tools(settings: Settings) -> set[str]:
    """Herramientas que no deben listarse ni ejecutarse (p. ej. autoruteo off)."""
    return {"autoroute_board"} if not settings.autoroute_enabled else set()


def _tool_schema(parameters: dict) -> dict:
    """OpenAI-style parameters → JSON Schema para MCP inputSchema."""
    if not parameters:
        return {"type": "object", "properties": {}}
    schema = dict(parameters)
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    return schema


def refresh_runtime_settings(settings: Settings) -> None:
    """Actualiza autoruteo/Java/fab desde Ajustes sin recrear el proceso MCP."""
    from kicad_ia.user_prefs import load_prefs, prefs_path

    if prefs_path().is_file():
        settings.apply_prefs(load_prefs())


def build_server(settings: Settings | None = None, gateway=None, registry: ToolRegistry | None = None) -> Server:
    """Construye el Server MCP con list_tools / call_tool sobre el registry del plugin."""
    settings = settings or Settings.from_env()
    registry = registry or build_registry()
    if gateway is None:
        gateway = SerializedGateway(open_gateway(settings))

    server = Server(
        "kicad-ia",
        instructions=INSTRUCTIONS,
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        refresh_runtime_settings(settings)
        blocked = excluded_tools(settings)
        tools: list[types.Tool] = []
        for item in registry.openai_tools(exclude=blocked):
            fn = item["function"]
            tools.append(
                types.Tool(
                    name=fn["name"],
                    description=fn.get("description") or "",
                    inputSchema=_tool_schema(fn.get("parameters") or {}),
                )
            )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        refresh_runtime_settings(settings)
        underlying = getattr(gateway, "inner", gateway)
        if hasattr(underlying, "_settings"):
            underlying._settings = settings
        blocked = excluded_tools(settings)
        result = await asyncio.to_thread(registry.call, name, arguments or {}, gateway, blocked)
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = json.dumps(
                {
                    "ok": result.get("ok") if isinstance(result, dict) else False,
                    "truncated": True,
                    "preview": text[: MAX_RESULT_CHARS // 2],
                    "keys": sorted(result.keys()) if isinstance(result, dict) else [],
                },
                ensure_ascii=False,
            )
        return [types.TextContent(type="text", text=text)]

    return server


async def run_stdio(settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    gateway = SerializedGateway(open_gateway(settings))
    server = build_server(settings, gateway)
    caps = await asyncio.to_thread(gateway.capabilities)
    log.info(
        "MCP KiCad IA listo (backend=%s, autoroute=%s, tools filtradas según Ajustes)",
        caps.get("backend"),
        settings.autoroute_enabled,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
