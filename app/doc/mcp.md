# MCP — KiCad IA

Expone las herramientas de `tools/registry.py` a clientes MCP (Cursor, Claude Desktop, etc.) por **stdio**.

## Requisitos

- `pip install -e ".[mcp,kicad]"` (SDK `mcp>=1.9,<2`)
- KiCad abierto con API IPC (salvo `KICAD_MODE=fake`)
- Mismo árbol `app/` y preferencias que el chat

## Arranque manual

```bash
cd app
source .venv/bin/activate
python -m kicad_ia.mcp
# o: kicad-ia-mcp
```

Logs van a **stderr** (stdout es el protocolo MCP).

## Cursor

1. Copia [mcp.cursor.example.json](mcp.cursor.example.json) a:
   - `.cursor/mcp.json` en el workspace, o
   - `~/.cursor/mcp.json` global
2. Sustituye las rutas absolutas a `.venv/bin/python` y a `app/`.
3. Reinicia MCP / Cursor y comprueba el servidor `kicad-ia`.

Ejemplo:

```json
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
```

## Comportamiento

| Tema | Detalle |
|------|---------|
| Herramientas | Las del registro (`inspect_context`, `place_circuit`, `ipc_*`, …) |
| Autoruteo | Solo si Ajustes / `AUTOROUTE_ENABLED` lo activó |
| Resultados | JSON en `TextContent`; respuestas muy grandes se truncan |
| Concurrencia | `SerializedGateway` igual que el chat |
| Prefs | Se refrescan en cada `list_tools` / `call_tool` |
| Escribir circuito | `place_circuit` exige antes `commit_intent` y `select_component` por cada lib_id (con huella verificada). La memoria es una por proceso MCP. Ver [agents.md](agents.md) |

## Código

- `src/kicad_ia/mcp/__init__.py` — `build_server`, `run_stdio`, `main`
- `src/kicad_ia/mcp/__main__.py` — `python -m kicad_ia.mcp`
- Pruebas: `tests/test_mcp.py`

No añadir herramientas solo en MCP: siempre al registro y a ambos gateways.
