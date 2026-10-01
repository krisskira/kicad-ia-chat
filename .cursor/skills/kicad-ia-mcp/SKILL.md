---
name: kicad-ia-mcp
description: >-
  Servidor MCP stdio de KiCad IA para Cursor u otros LLM. Usar al tocar
  app/src/kicad_ia/mcp/, doc/mcp.md, o la plantilla mcp.cursor.example.json.
---

# Skill: MCP KiCad IA

Leer [app/doc/mcp.md](../../../app/doc/mcp.md) y [app/AGENTS.md](../../../app/AGENTS.md).

## Alcance

- `src/kicad_ia/mcp/` — `build_server`, `run_stdio`
- `doc/mcp.md`, `doc/mcp.cursor.example.json`
- Extra de empaquetado: `pip install -e ".[mcp]"` (`mcp>=1.9,<2`)

## Reglas

- **No** duplicar herramientas: mismo `build_registry()` que el chat.
- Filtrar `autoroute_board` según Ajustes (`excluded_tools`).
- Logs a stderr; stdout es el protocolo.
- Resultados JSON en `TextContent`; truncar si son enormes.
- Tras cambiar el contrato de tools, actualizar pruebas `tests/test_mcp.py`.

## Comprobar

```bash
cd app && .venv/bin/pytest tests/test_mcp.py
# Manual: python -m kicad_ia.mcp  (con KiCad o KICAD_MODE=fake)
```
