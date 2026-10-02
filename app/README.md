# KiCad IA

Chat para construir el esquemático, pasarlo a la placa y consultar lo que está seleccionado. Las piezas salen de las bibliotecas que tienes configuradas en KiCad, no de una lista del plugin.

Guía para agentes: [AGENTS.md](AGENTS.md) · Arquitectura: [doc/architecture.md](doc/architecture.md) · Agentes y flujos: [doc/agents.md](doc/agents.md) · MCP: [doc/mcp.md](doc/mcp.md) · Roadmap: [doc/roadmap.md](doc/roadmap.md)

## Instalación

Requisitos: **KiCad 10**, red la primera vez (KiCad instala `requirements.txt` en su entorno) y, solo si activas el autoruteo, **Java 17+**. Abre KiCad una vez antes de instalar para que exista `Documentos/KiCad/<versión>/`.

Los scripts y la copia manual dejan el plugin en `Documentos/KiCad/<versión>/plugins/kicad-ia` (no en `scripting/plugins`); el Gestor lo guarda en su propia carpeta de complementos. Usa una sola vía. Después: reinicia KiCad, abre el editor de PCB, pulsa **KiCad IA** y configura el modelo en Ajustes.

### Gestor de complementos

1. En KiCad: Preferencias → Gestor de complementos → repositorios.
2. Añade:

```text
https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/app/packaging/repository.json
```

3. Instala **KiCad IA**, reinicia y abre el editor de PCB.

### Script (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.sh | sh
```

O bájalo, léelo y ejecútalo:

```bash
curl -fsSL https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.sh -o install.sh
less install.sh
sh install.sh
```

Opciones: `--version 0.1.0`, `--kicad-version 10.0`, `--uninstall`.

### Script (Windows)

En PowerShell:

```powershell
irm https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.ps1 | iex
```

O descarga `install/install.ps1`, revísalo y ejecuta `.\install.ps1`. Parámetros: `-Version 0.1.0`, `-KicadVersion 10.0`, `-Uninstall`.

### Copia manual

1. En [Releases](https://github.com/krisskira/kicad-ia-chat/releases) descarga `kicad-ia-<versión>.zip` (no el `-pcm.zip`).
2. Descomprímelo en:

```text
~/Documents/KiCad/<versión>/plugins/kicad-ia
```

En Windows: `Documentos\KiCad\<versión>\plugins\kicad-ia`. La carpeta debe contener `plugin.json` e `ipc_entry.py` en la raíz.

### Desde el código (desarrollo)

```bash
python app/scripts/link_plugin.py
```

Enlaza esta carpeta en `~/Documents/KiCad/<versión>/plugins/kicad-ia`. Iconos: `python3 app/scripts/make_icons.py`. Empaquetado local: `python app/scripts/package_release.py --validate`. En macOS KiCad usa Python 3.9 (`eval_type_backport` en `requirements.txt`).

### Releases

Cada push o merge a `main` que toque lo que va en el ZIP (`app/src`, `app/icons`, `plugin.json`, `ipc_entry.py`, `requirements.txt`, `packaging/metadata.json`) crea el tag siguiente (`.github/workflows/version.yml`). El nivel sale de Conventional Commits: `feat!:` o `BREAKING CHANGE` → major (minor en 0.x), `feat:` → minor, el resto → patch. Desde Actions se puede forzar el nivel.

El tag dispara `.github/workflows/release.yml`: construye los ZIP, crea el release (nunca reemplaza los ZIP de un tag existente) y escribe en `main` el índice PCM calculado desde el ZIP publicado, junto con la versión de `pyproject.toml`. Relanzarlo a mano con un tag existente repara el índice.

`packages.json` y `repository.json` los genera CI: no se editan a mano. Lo que describe el paquete va en `packaging/metadata.json`.

Para que el push del tag dispare el release directamente, crea el secreto `RELEASE_TOKEN` (PAT con Contents y Actions en escritura; si `main` está protegida, con permiso para saltar la protección). Sin él, `version.yml` lanza el release por `workflow_dispatch`.

## Arranque

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,kicad,mcp]"
cp .env.example .env   # opcional si usas ⚙ Ajustes
python -m kicad_ia
```

El chat queda en `http://127.0.0.1:8765`. El navegador abre un WebSocket en `/ws`: el servidor vigila KiCad cada `WATCH_INTERVAL` s (1,5 por defecto) y solo avisa cuando cambian conexión, proyecto o selección. El chat enseña cada herramienta mientras corre. Si se corta, la página se reconecta sola. Si KiCad se cierra o arranca después, el servidor se reconecta sin reiniciar.

`KICAD_MODE=auto` usa KiCad si la API responde; si no, modo memoria de prueba. `fake` no intenta conectar. `live` exige KiCad.

## Ajustes (UI)

En **⚙** del chat puedes configurar, sin editar `.env`:

| Bloque | Campos |
|--------|--------|
| LLM | Preset (Gemini / Ollama / OpenAI / personalizado), URL, API key, modelo, modelo revisor |
| Java | Ruta de `java` + botón Detectar (macOS/Homebrew/JVMs) |
| Autoruteo | Activar/desactivar; si está on: anchos mínimos de pista, clearance, vía, taladro y agujero (mm) |

Se guardan en `~/Library/Application Support/kicad-ia/user-settings.json` (macOS) o `~/.config/kicad-ia/` (Linux) y tienen prioridad sobre `.env`.

También puedes usar variables:

```bash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=...
LLM_MODEL=gemini-3.5-flash-lite
# LLM_REVIEW_MODEL=gemini-3.5-flash
# JAVA_BIN=
# AUTOROUTE_ENABLED=0
```

`LLM_REVIEW_MODEL` revisa cada `place_circuit` antes de escribir (hasta dos rechazos por mensaje). Ante un 429 el cliente espera y reintenta. Sin modelo siguen `/estado`, `/seleccion` y `/herramientas`.

## MCP (Cursor y otros LLM)

Las mismas herramientas se publican por **MCP stdio** para que Cursor u otro agente actúen sobre KiCad sin el LLM interno del chat. Detalle: [doc/mcp.md](doc/mcp.md).

```bash
pip install -e ".[mcp,kicad]"
# KiCad abierto con API IPC
python -m kicad_ia.mcp
```

Copia [doc/mcp.cursor.example.json](doc/mcp.cursor.example.json) a `.cursor/mcp.json` (rutas absolutas al `.venv` y a `app/`). El autoruteo solo aparece si lo activaste en Ajustes. Chat web y MCP pueden convivir.

## Cómo trabaja con KiCad 10

| Parte | Cómo |
|---|---|
| Bibliotecas | `sym-lib-table` / `fp-lib-table` del usuario y del proyecto. |
| Esquemático | Escritura del `.kicad_sch` con copia en `.kicad-ia-backup/`. Editor de esquemáticos cerrado. |
| Validación | Pre-escritura + ERC/netlist con `kicad-cli`. |
| Placa | API IPC (`kipy`): selección, huellas, cobre, 3D. |
| Imágenes | `render_view` → `kicad-cli`; servidas en `/renders`. |
| Organizar | `organize_layout` por función (esquemático y/o PCB). |
| Colocación IPC | `ipc_place_components`: preview → confirmación. Pre-chequeo Clase 2, no certificación. |
| Autoruteo | Off por defecto. FreeRouting **2.0.1** + Java 17+; DSN/SES vía `pcbnew`; candidato + DRC antes de aplicar. |
| Validar IPC | `ipc_validate_correct`; `apply=true` solo correcciones seguras. |
| Esquemático → PCB | F8 en el editor. `kipy` 0.8 no importa netlists. `sync_board` devuelve el área de la placa (Edge.Cuts o rectángulo propuesto en mm). |
| Intención | `commit_intent` guarda lo que pidió el usuario; `place_circuit` no lo contradice. |
| Selección | `select_component`: símbolo de la biblioteca con huella verificada (existe y tiene pads para cada pin). Si falta, propone huellas reales y pregunta el encapsulado. |
| Tokens | Cabecera del chat, a la derecha del modelo. Si el proveedor no informa el consumo, el número es una estimación y lleva `~`. |
| Conversaciones | Se guardan solas. La barra lateral las lista y permite abrirlas o borrarlas. |

## Qué puede pedir

- «Diseña un ESP32-S3 con ILI9341 por SPI y 18650 con regulador a 3,3 V.»
- «¿Qué huella y modelo 3D tiene lo seleccionado?»
- «Valida el esquemático y dime qué falta para la placa.»
- «Enséñame la placa en 3D.» / «Organiza por funciones.»
- «Coloca con IPC Clase 2; primero la propuesta.»
- «Autorutea, valida con DRC y no apliques hasta que confirme.»
- «Valida IPC y corrige solo lo seguro.»
- «Busca esta pantalla en LCSC.» → confirmas el código C → `import_lcsc`.

## Pruebas

```bash
cd app && .venv/bin/pytest
```

No necesitan KiCad (`FakeGateway` + biblioteca de ejemplo en `tests/conftest.py`).

## Mapa del código

| Ruta | Rol |
|---|---|
| `packaging/` | Índice PCM (`repository.json`, `packages.json`, `metadata.json`) |
| `src/kicad_ia/agent/` | Bucle LLM, revisores, cliente HTTP y contador de tokens |
| `src/kicad_ia/agent/intent.py` | Contrato de intención y guardia de `place_circuit` |
| `src/kicad_ia/agent/components.py` | Selección de componentes y validación de huellas |
| `src/kicad_ia/kicad/board_area.py` | Área de placa para el paso a PCB |
| `src/kicad_ia/tools/registry.py` | Contrato de herramientas (chat + MCP) |
| `src/kicad_ia/kicad/kipy_gateway.py` | KiCad real |
| `src/kicad_ia/kicad/fake.py`, `catalog.py` | Backend de prueba |
| `src/kicad_ia/kicad/serialized.py` | Un hilo a la vez hacia KiCad |
| `src/kicad_ia/kicad/sch_writer.py` | Escritura/validación del esquemático |
| `src/kicad_ia/kicad/libraries.py` | Tablas, búsqueda, pines, 3D |
| `src/kicad_ia/kicad/lcsc.py` | LCSC / EasyEDA |
| `src/kicad_ia/kicad/layout.py` | Grupos funcionales |
| `src/kicad_ia/kicad/ipc.py` | Pre-chequeo y colocación IPC |
| `src/kicad_ia/kicad/freerouting.py` | JAR + Java + pipeline |
| `src/kicad_ia/kicad/pcbnew_bridge.py` | DSN/SES / reglas fab |
| `src/kicad_ia/kicad/copper_apply.py` | Aplicar cobre del candidato |
| `src/kicad_ia/kicad/candidates.py` | Candidatos preview/apply |
| `src/kicad_ia/mcp/` | Servidor MCP stdio |
| `src/kicad_ia/user_prefs.py` | Persistencia de Ajustes |
| `src/kicad_ia/events.py` | Bus de eventos |
| `src/kicad_ia/services/` | Chat + vigilante |
| `src/kicad_ia/server/` | FastAPI, `/ws`, UI estática |
| `doc/` | Arquitectura, agentes y flujos, MCP, roadmap |
