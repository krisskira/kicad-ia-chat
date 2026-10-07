**English** · [Español](README.es.md)

# KiCad IA

A chat that builds the schematic, moves it to the board, and inspects what is selected. Parts come from the libraries configured in KiCad, not from a list inside the plugin.

Agent guide: [AGENTS.md](AGENTS.md) · Architecture: [doc/architecture.md](doc/architecture.md) · The board: [doc/placa.md](doc/placa.md) · Agents and flows: [doc/agents.md](doc/agents.md) · MCP: [doc/mcp.md](doc/mcp.md) · Roadmap: [doc/roadmap.md](doc/roadmap.md)

## Installation

Requirements: **KiCad 10**, a network connection the first time (KiCad installs `requirements.txt` into its environment) and, only if you turn autorouting on, **Java 17+**. Open KiCad once before installing so that `Documents/KiCad/<version>/` exists.

The scripts and the manual copy put the plugin in `Documents/KiCad/<version>/plugins/kicad-ia` (not in `scripting/plugins`); the Plugin Manager stores it in its own plugins folder. Use only one method. Then restart KiCad, open the PCB editor, click **KiCad IA**, and set the model in Settings.

### Plugin and Content Manager

1. In KiCad: Preferences → Plugin and Content Manager → repositories.
2. Add:

```text
https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/app/packaging/repository.json
```

3. Install **KiCad IA**, restart, and open the PCB editor.

### Script (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.sh | sh
```

Or download it, read it, and run it:

```bash
curl -fsSL https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.sh -o install.sh
less install.sh
sh install.sh
```

Options: `--version 0.1.0`, `--kicad-version 10.0`, `--uninstall`.

### Script (Windows)

In PowerShell:

```powershell
irm https://raw.githubusercontent.com/krisskira/kicad-ia-chat/main/install/install.ps1 | iex
```

Or download `install/install.ps1`, review it, and run `.\install.ps1`. Parameters: `-Version 0.1.0`, `-KicadVersion 10.0`, `-Uninstall`.

### Manual copy

1. From [Releases](https://github.com/krisskira/kicad-ia-chat/releases) download `kicad-ia-<version>.zip` (not the `-pcm.zip`).
2. Unzip it into:

```text
~/Documents/KiCad/<version>/plugins/kicad-ia
```

On Windows: `Documents\KiCad\<version>\plugins\kicad-ia`. The folder must contain `plugin.json` and `ipc_entry.py` at its root.

### From the source (development)

```bash
python app/scripts/link_plugin.py
```

Links this folder into `~/Documents/KiCad/<version>/plugins/kicad-ia`. Icons: `python3 app/scripts/make_icons.py`. Local packaging: `python app/scripts/package_release.py --validate`. On macOS KiCad uses Python 3.9 (`eval_type_backport` in `requirements.txt`).

### Releases

Each push or merge to `main` that touches what goes into the ZIP (`app/src`, `app/icons`, `plugin.json`, `ipc_entry.py`, `requirements.txt`, `packaging/metadata.json`) creates the next tag (`.github/workflows/version.yml`). The level comes from Conventional Commits: `feat!:` or `BREAKING CHANGE` → major (minor on 0.x), `feat:` → minor, anything else → patch. The level can be forced from Actions.

The tag starts `.github/workflows/release.yml`: it builds the ZIPs, creates the release (it never replaces the ZIPs of an existing tag), and writes to `main` the PCM index computed from the published ZIP, together with the version in `pyproject.toml`. Running it again by hand with an existing tag repairs the index.

CI generates `packages.json` and `repository.json`: do not edit them by hand. What describes the package lives in `packaging/metadata.json`.

The index is published to `main` with the Actions token. In the repository, Settings → Actions → General → Workflow permissions must be **Read and write permissions**. If `main` has a ruleset, add **GitHub Actions** to its Bypass list.

`RELEASE_TOKEN` is optional. If it exists and can create tags, the tag starts the release; otherwise `version.yml` creates the tag and starts the release.

## Running it

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,kicad,mcp]"
cp .env.example .env   # optional if you use ⚙ Settings
python -m kicad_ia
```

The chat is at `http://127.0.0.1:8765`. The browser opens a WebSocket on `/ws`: the server watches KiCad every `WATCH_INTERVAL` seconds (1.5 by default) and only notifies when connection, project, or selection changes. The chat shows each tool while it runs. If the connection drops, the page reconnects on its own. If KiCad closes or starts later, the server reconnects without a restart.

`KICAD_MODE=auto` uses KiCad when the API answers; otherwise it falls back to an in-memory test mode. `fake` does not try to connect. `live` requires KiCad.

## Settings (UI)

In the chat's **⚙** you can configure this without editing `.env`:

| Block | Fields |
|--------|--------|
| LLM | Preset (Gemini / Ollama / OpenAI / custom), URL, API key, model, reviewer model |
| Java | Path to `java` + Detect button (macOS/Homebrew/JVMs) |
| Autoroute | On/off; when on: minimum track width, clearance, via, drill, and hole (mm) |

They are stored in `~/Library/Application Support/kicad-ia/user-settings.json` (macOS) or `~/.config/kicad-ia/` (Linux) and take priority over `.env`. The interface language (English by default, Spanish with **ES** in the top bar) is stored in the browser, not in that JSON.

You can also use variables:

```bash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=...
LLM_MODEL=gemini-3.5-flash-lite
# LLM_REVIEW_MODEL=gemini-3.5-flash
# JAVA_BIN=
# AUTOROUTE_ENABLED=0
```

`LLM_REVIEW_MODEL` is optional: same URL and key as the orchestrator, a different model name. It reviews each `place_circuit` after the hard rules (up to two rejections per message). Empty = code only. On a 429 the client waits and retries. Without a main model, `/status`, `/selection`, and `/tools` still work (`/estado`, `/seleccion`, and `/herramientas` too).

## MCP (Cursor and other LLMs)

The same tools are published over **MCP stdio** so Cursor or another agent can act on KiCad without the chat's internal LLM. Detail: [doc/mcp.md](doc/mcp.md).

```bash
pip install -e ".[mcp,kicad]"
# KiCad open with the IPC API
python -m kicad_ia.mcp
```

Copy [doc/mcp.cursor.example.json](doc/mcp.cursor.example.json) to `.cursor/mcp.json` (absolute paths to the `.venv` and to `app/`). Autoroute appears only if you turned it on in Settings. The web chat and MCP can run together.

## How it works with KiCad 10

| Part | How |
|---|---|
| Libraries | The user's and the project's `sym-lib-table` / `fp-lib-table`. |
| Schematic | Writes `.kicad_sch` with a copy in `<project>-backups/kicad-ia/`. Schematic editor closed. |
| Validation | Pre-write check + ERC/netlist with `kicad-cli`. |
| Board | IPC API (`kipy`): selection, footprints, copper, 3D. |
| Images | `render_view` → `kicad-cli`; served under `/renders`. |
| Arrange | `organize_layout` by function (schematic and/or PCB). |
| IPC placement | `ipc_place_components`: preview → confirmation. Class 2 pre-check, not a certification. |
| Autoroute | Off by default. FreeRouting **2.0.1** + Java 17+; DSN/SES through `pcbnew`; candidate + DRC before applying. |
| IPC validate | `ipc_validate_correct`; `apply=true` only for safe fixes. |
| Schematic → PCB | F8 in the editor. `kipy` 0.8 does not import netlists. `sync_board` returns the board area (Edge.Cuts or a proposed rectangle in mm). |
| Intent | `commit_intent` stores what the user asked; `place_circuit` does not contradict it. |
| Selection | `select_component`: a library symbol with a verified footprint (it exists and has pads for every pin). If it is missing, it proposes real footprints and asks for the package. |
| Tokens | Chat header, to the right of the model. If the provider does not report usage, the number is an estimate and is marked with `~`. |
| Conversations | Saved on their own. The sidebar lists them and can open or delete them. |
| Language | English by default. **ES** in the top bar switches the UI and the assistant's replies. Strings live in `server/static/i18n.js` and `i18n.py`. |

## What you can ask

- "Design an ESP32-S3 with an ILI9341 over SPI and a 18650 with a 3.3 V regulator."
- "What footprint and 3D model does the selection have?"
- "Validate the schematic and tell me what is missing for the board."
- "Show me the board in 3D." / "Arrange by function."
- "Place with IPC Class 2; show the proposal first."
- "Autoroute, validate with DRC, and do not apply until I confirm."
- "Validate IPC and fix only what is safe."
- "Search LCSC for this display." → you confirm the C code → `import_lcsc`.

## Tests

```bash
cd app && .venv/bin/pytest
```

They do not need KiCad (`FakeGateway` + the sample library in `tests/conftest.py`).

## Code map

| Path | Role |
|---|---|
| `packaging/` | PCM index (`repository.json`, `packages.json`, `metadata.json`) |
| `src/kicad_ia/agent/` | LLM loop, reviewers, HTTP client, and token counter |
| `src/kicad_ia/agent/intent.py` | Intent contract and the `place_circuit` guard |
| `src/kicad_ia/agent/components.py` | Component selection and footprint checks |
| `src/kicad_ia/kicad/board_area.py` | Board area for the step to the PCB |
| `src/kicad_ia/tools/registry.py` | Tool contract (chat + MCP) |
| `src/kicad_ia/kicad/kipy_gateway.py` | Real KiCad |
| `src/kicad_ia/kicad/fake.py`, `catalog.py` | Test backend |
| `src/kicad_ia/kicad/serialized.py` | One thread at a time toward KiCad |
| `src/kicad_ia/kicad/sch_writer.py` | Schematic write and validation |
| `src/kicad_ia/kicad/libraries.py` | Tables, search, pins, 3D |
| `src/kicad_ia/kicad/lcsc.py` | LCSC / EasyEDA |
| `src/kicad_ia/kicad/layout.py` | Functional groups |
| `src/kicad_ia/kicad/ipc.py` | IPC pre-check and placement |
| `src/kicad_ia/kicad/freerouting.py` | JAR + Java + pipeline |
| `src/kicad_ia/kicad/pcbnew_bridge.py` | DSN/SES / fab rules |
| `src/kicad_ia/kicad/copper_apply.py` | Apply a candidate's copper |
| `src/kicad_ia/kicad/candidates.py` | Preview/apply candidates |
| `src/kicad_ia/mcp/` | MCP stdio server |
| `src/kicad_ia/i18n.py` | Chat strings the user sees (English and Spanish) |
| `src/kicad_ia/user_prefs.py` | Settings persistence |
| `src/kicad_ia/events.py` | Event bus |
| `src/kicad_ia/services/` | Chat + watcher |
| `src/kicad_ia/server/` | FastAPI, `/ws`, static UI (`static/i18n.js`, EN/ES switch) |
| `doc/` | Architecture, agents and flows, MCP, roadmap |
