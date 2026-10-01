# Arquitectura — KiCad IA

## Capas

```
UI (static/) ──WebSocket/HTTP──► server/app.py
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              services/chat    services/watcher    /api/settings
                    │                 │
                    ▼                 ▼
              agent/loop + dispatch   EventBus → hub → /ws
                    │
                    ▼
              tools/registry.py  ◄─── mismo contrato ───► mcp/ (stdio)
                    │
                    ▼
              SerializedGateway
                 ├── KipyGateway (KiCad real)
                 └── FakeGateway (pruebas / sin editor)
```

## Gateways

| Clase | Rol |
|-------|-----|
| `Gateway` | Contrato abstracto |
| `KipyGateway` | Placa por IPC (`kipy`); esquemático por archivo; DRC/ERC/render con `kicad-cli` |
| `FakeGateway` | Mismo contrato en memoria + `catalog.py` |
| `SerializedGateway` | Un hilo a la vez; permite `swap` al reconectar |

`capabilities()` debe decir solo lo que funciona. El modo `KICAD_MODE`: `auto` | `live` | `fake`.

## Flujo de chat

1. Cliente envía `chat.send` por `/ws`.
2. `ChatService` lanza un turno en hilo; publica `turn.started` / `llm.*` / `tool.*` / `turn.finished`.
3. `run_turn` llama al LLM con `registry.openai_tools(exclude=…)`; cada tool pasa por el handler del registro.
4. `CircuitReviewer` puede bloquear `place_circuit`; `PcbReviewer` valida candidatos de PCB.

## PCB seguro (IPC + autoruteo)

1. Operación en **copia** / candidato (`CandidateStore`).
2. Vista previa: métricas, DRC, imagen, `candidate_id`.
3. Usuario confirma → segunda llamada `apply=true` + `candidate_id`.
4. Si DRC empeora o el revisor rechaza, no se aplica a la placa viva.

Autoruteo: placa → DSN (`pcbnew_bridge`) → FreeRouting JAR → SES → candidato → DRC/IPC. Java se resuelve con detección ampliada o ruta en Ajustes. FreeRouting fijado a **2.0.1** (respeta `-mp` en headless).

## Ajustes

- UI ⚙ → `PUT /api/settings` → `user_prefs.py` (`~/Library/Application Support/kicad-ia/user-settings.json` en macOS).
- Prioridad sobre `.env` para LLM, Java, autoruteo y reglas fab.
- Chat y MCP releen prefs al listar/llamar herramientas afectadas.

## Eventos

Tipos en `events.py`: `status`, `selection`, `turn.*`, `tool.*`, `llm.*`. El vigilante solo publica si el contenido cambió (sin timestamps volátiles en el payload comparable).

## MCP

Ver [mcp.md](mcp.md). Mismo `build_registry()` y `open_gateway()`; transporte stdio JSON-RPC.
