<!-- KiCad IA plugin — keep under ~180 lines -->
<!-- Last updated: 2026-10-06 -->

# KiCad IA (plugin)

Trabaja en `app/`. El README público y la landing están en la raíz (`AGENTS.md` raíz + skill `kicad-ia-pagina`).

## Stack

- Python ≥ 3.9 · FastAPI · WebSocket `/ws`
- KiCad 10 vía `kipy` (placa) + escritura de `.kicad_sch` por archivo
- LLM: cualquier API compatible con OpenAI `/chat/completions`
- FreeRouting 2.0.1 (JAR verificado, Java 17+)
- MCP stdio: `python -m kicad_ia.mcp` (Cursor y otros clientes)

## Docs

| Doc | Contenido |
|-----|-----------|
| [README.md](README.md) | Arranque, Ajustes, MCP, mapa de código |
| [doc/architecture.md](doc/architecture.md) | Capas, gateways, eventos, flujo seguro PCB |
| [doc/placa.md](doc/placa.md) | Cómo se genera la placa: orquestador, vista previa, revisor, autoruteo |
| [doc/agents.md](doc/agents.md) | Orquestador, intención, selección de componentes, huellas, área de placa, tokens |
| [doc/agente-coste.md](doc/agente-coste.md) | Coste del bucle, caché y por qué no migrar a un framework |
| [doc/mcp.md](doc/mcp.md) | Servidor MCP y config Cursor |
| [doc/roadmap.md](doc/roadmap.md) | Pendientes (bibliotecas, agentes, KiCad 11) |
| [doc/mcp.cursor.example.json](doc/mcp.cursor.example.json) | Plantilla `.cursor/mcp.json` |

## Skills / agentes

| Skill / agente | Uso |
|----------------|-----|
| **kicad-ia-plugin** | Chat, registry, gateways, esquemático, UI, Ajustes |
| **kicad-ia-pcb** | IPC, colocación, autoruteo FreeRouting, DRC, candidatos |
| **kicad-ia-mcp** | Servidor MCP stdio, integración Cursor |
| kicad-ia-pagina | Solo portada/landing (raíz del repo) |

Agentes en `.cursor/agents/` delegan al skill homónimo.

## Critical Rules

- ALWAYS la UI del chat en inglés por defecto y en español, con el selector EN/ES de la barra superior (`server/static/i18n.js`). Cada texto nuevo de la interfaz va en los dos idiomas. El modelo responde en el idioma elegido.
- ALWAYS herramientas nuevas en `registry.py` **y** en `KipyGateway` + `FakeGateway`.
- ALWAYS `capabilities()` refleja lo real; nunca inventar métodos de `kipy`.
- ALWAYS esquemático: editor cerrado, backup en `<proyecto>-backups/kicad-ia/`, validar antes de escribir.
- ALWAYS KiCad solo vía `SerializedGateway` (kipy no es thread-safe).
- ALWAYS `ipc_place_components` / `autoroute_board` con `apply=false` primero; aplicar solo con `candidate_id` y confirmación.
- ALWAYS `autoroute_board` oculto si Ajustes no activó autoruteo + reglas fab.
- ALWAYS informes IPC = pre-chequeo Clase 2, no certificación.
- ALWAYS MCP reutiliza el mismo `registry`/gateway; no duplicar herramientas.
- ALWAYS `place_circuit` pasa por `guard_place`: contrato de intención, símbolos de `select_component` y huella verificada.
- ALWAYS al pasar a la placa, repetir `board_area.must_tell_user` (rectángulo de Edge.Cuts o la orden de medir).
- NEVER aceptar un componente sin huella verificada (salvo `power:*`) ni marcar como PASS un dato que no se leyó.
- NEVER secretos en el repo; API keys en Ajustes o `.env`.
- NEVER editar a mano `packaging/packages.json` ni `packaging/repository.json`: los genera `release.yml` desde el ZIP publicado. Cambios del paquete en `packaging/metadata.json`.
- NEVER afirmar cambios en KiCad si `ok: false` o backend `fake`.
- NEVER `run_action` del router sin petición explícita y nombre de acción.

## Development

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,kicad,mcp]"
cp .env.example .env   # o configura ⚙ Ajustes
python -m kicad_ia     # chat http://127.0.0.1:8765
python -m kicad_ia.mcp # MCP stdio (Cursor)
.venv/bin/pytest
```
