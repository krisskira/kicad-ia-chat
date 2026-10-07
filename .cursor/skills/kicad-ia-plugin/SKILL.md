---
name: kicad-ia-plugin
description: >-
  Desarrollo del plugin KiCad IA: chat WebSocket, registry de herramientas,
  gateways Kipy/Fake, escritor de esquemático, Ajustes (LLM/Java), UI estática.
  Usar al tocar app/src/kicad_ia fuera de PCB/MCP dedicados, o al añadir tools.
---

# Skill: plugin KiCad IA

Leer primero [app/AGENTS.md](../../../app/AGENTS.md) y [app/doc/architecture.md](../../../app/doc/architecture.md).

## Alcance

- `tools/registry.py` — contrato del modelo / MCP
- `kicad/kipy_gateway.py`, `fake.py`, `session.py`, `serialized.py`
- `kicad/sch_writer.py`, `libraries.py`, `lcsc.py`, `layout.py`, `render.py`, `cli.py`
- `agent/` (loop, history, dispatch, llm + `TokenMeter`/`usage_log`, review de circuito)
- `agent/intent.py` (contrato, `guard_place`) y `agent/components.py` (selección + huella obligatoria). Flujos en [app/doc/agents.md](../../../app/doc/agents.md); la placa, en [app/doc/placa.md](../../../app/doc/placa.md); el coste del bucle, en [app/doc/agente-coste.md](../../../app/doc/agente-coste.md). Actualízalos si cambias una decisión.
- `kicad/layout.py` (`plan_stages`, marcos elegibles) al tocar `organize_layout`
- `server/` (FastAPI, `/ws`, static UI, `/api/settings`)
- `config.py`, `user_prefs.py`, `services/`

PCB IPC/autoruteo → skill **kicad-ia-pcb**. MCP → **kicad-ia-mcp**. Landing → **kicad-ia-pagina**.

## Checklist al añadir una herramienta

1. Handler + esquema en `registry.py`.
2. Método en `Gateway`, implementación en `KipyGateway` y `FakeGateway`.
3. `capabilities()` si aplica.
4. Prueba con `FakeGateway` (sin KiCad).
5. Texto de UI en `server/static/i18n.js` (inglés y español) si el usuario la ve en pasos.

## Ajustes

Persistencia en `user_prefs.py`. API `GET/PUT /api/settings`, `POST /api/settings/probe-java`. Tras guardar, el chat refresca el cliente LLM (`ChatService.apply_runtime`).

## Comprobar

```bash
cd app && .venv/bin/pytest
```

Tras tocar el escritor: ERC con `kicad-cli sch erc` en un proyecto de prueba.
