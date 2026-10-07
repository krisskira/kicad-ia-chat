"""Fotogramas de los dos recorridos.

El chat es la interfaz real del plugin (`python -m kicad_ia` en modo de
pruebas, con un directorio de ajustes temporal). Los mensajes se inyectan con
las mismas funciones que usa el WebSocket, así que cada pantalla es lo que el
chat pinta. Las imágenes del esquemático y de la placa salen del proyecto que
arma `proyecto_demo.py` con KiCad 10.

El editor de PCB es una ilustración: la ventana es un dibujo, la placa dentro
es el SVG real que exporta kicad-cli.

Desde la raíz del repositorio, después de `proyecto_demo.py`:

  PYTHONPATH=app/src app/.venv/bin/python landing-page/resources/recorridos/capturas.py

Escribe `landing-page/public/media/recorridos/<recorrido>/<idioma>/NN-<escena>.webp`
y los PNG para el video en /tmp/kicad-ia-recorrido/fotogramas.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from cdp import Browser, data_url

HERE = Path(__file__).resolve().parent
LANDING = HERE.parents[1]
REPO = LANDING.parent
APP = REPO / "app"
OUT = LANDING / "public" / "media" / "recorridos"
CHAT_W, CHAT_H = 1280, 800
JAVA_SHOWN = "/usr/bin/java"

CROP = r"""
((text, box) => {
  const holder = document.createElement('div');
  holder.innerHTML = text;
  document.body.append(holder);
  const svg = holder.querySelector('svg');
  if (!box) {
    // El fondo de página es un rect del tamaño de la hoja: no cuenta como dibujo.
    const page = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    const k = vb.width / page.width;
    let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
    for (const node of svg.querySelectorAll('path, text, circle, ellipse, polyline, polygon, line, rect')) {
      const r = node.getBoundingClientRect();
      if (!r.width && !r.height) continue;
      if (r.width > page.width * 0.9 && r.height > page.height * 0.9) continue;
      left = Math.min(left, r.left); top = Math.min(top, r.top);
      right = Math.max(right, r.right); bottom = Math.max(bottom, r.bottom);
    }
    const b = { x: vb.x + (left - page.left) * k, y: vb.y + (top - page.top) * k, width: (right - left) * k, height: (bottom - top) * k };
    const m = Math.max(b.width, b.height) * 0.05;
    box = { x: b.x - m, y: b.y - m, w: b.width + 2 * m, h: b.height + 2 * m };
  }
  svg.setAttribute('viewBox', `${box.x} ${box.y} ${box.w} ${box.h}`);
  svg.setAttribute('width', 1400);
  svg.setAttribute('height', Math.round((1400 * box.h) / box.w));
  const out = new XMLSerializer().serializeToString(svg);
  holder.remove();
  return { svg: out, box };
})
"""


def cropped(browser: Browser, path: Path, box: dict | None = None) -> tuple[str, dict]:
    """El SVG de kicad-cli trae la página entera; se recorta al dibujo."""
    text = path.read_text(encoding="utf-8")
    result = browser.js(f"{CROP}({json.dumps(text)}, {json.dumps(box)})")
    encoded = base64.b64encode(result["svg"].encode("utf-8")).decode()
    return f"data:image/svg+xml;base64,{encoded}", result["box"]

HELPERS = r"""
(() => {
  if (!window.__h) { window.__h = handle; handle = () => {}; }
  window.__T = 't0';
  window.__i = 0;
  window.__turn = (id) => { __T = id; __i = 0; __h({ type: 'turn.started', turn_id: id }); };
  window.__user = (text) => { els.welcome.hidden = true; addUser(text); };
  window.__tool = (tool, args, result) => {
    const index = __i++;
    __h({ type: 'tool.started', turn_id: __T, index, tool, arguments: args });
    if (result) __h({ type: 'tool.finished', turn_id: __T, index, tool, arguments: args, result });
    return index;
  };
  window.__finish = (index, tool, args, result) => __h({ type: 'tool.finished', turn_id: __T, index, tool, arguments: args, result });
  window.__say = (text) => __h({ type: 'llm.text', turn_id: __T, text });
  window.__done = () => { setBusy(false); hideTyping(); };
  window.__lbl = (id) => document.getElementById(id).closest('label');
  window.__last = (selector) => { const all = document.querySelectorAll(selector); return all[all.length - 1]; };
  window.__rect = (nodes) => {
    const list = (Array.isArray(nodes) ? nodes : [nodes]).filter(Boolean);
    if (!list.length) return null;
    const inside = list.every((node) => els.messages.contains(node));
    const clip = inside ? els.messages.getBoundingClientRect() : { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
    const boxes = list.map((node) => node.getBoundingClientRect());
    const x = Math.max(clip.left + 4, Math.min(...boxes.map((b) => b.left)));
    const y = Math.max(clip.top + 8, Math.min(...boxes.map((b) => b.top)));
    const r = Math.min(clip.right - 4, Math.max(...boxes.map((b) => b.right)));
    const bottom = Math.min(clip.bottom - 8, Math.max(...boxes.map((b) => b.bottom)));
    return { x, y, w: r - x, h: bottom - y };
  };
  window.__neutral = () => {
    document.getElementById('set-java').value = '__JAVA__';
    document.getElementById('settings-path').textContent = '__PATH__';
  };
  return true;
})()
"""


def status(summary: dict, java: dict, *, llm: bool, autoroute: bool, tokens: int) -> dict:
    return {
        "capabilities": {
            "connected": True,
            "backend": "kipy",
            "kicad_version": "10.0.1",
            "project": "led-usbc",
            "project_path": "/Users/demo/KiCad/led-usbc",
            "schematic_write": True,
            "schematic_open_in_editor": False,
            "board_open": True,
            "libraries": {
                "symbol_libraries": summary["symbol_libraries"],
                "footprint_libraries": summary["footprint_libraries"],
            },
            "erc": True,
            "notes": [],
        },
        "llm_ready": llm,
        "model": "gemini-2.5-flash" if llm else "",
        "review_model": "gemini-2.5-flash" if llm else "",
        "autoroute_enabled": autoroute,
        "java": java,
        "tokens": {
            "total": tokens,
            "prompt": int(tokens * 0.97),
            "completion": tokens - int(tokens * 0.97),
            "calls": max(0, tokens // 9000),
            "estimated": False,
        },
    }


def js_status(payload: dict) -> str:
    return f"renderStatus({json.dumps(payload, ensure_ascii=False)});"


def board_labels(lang: str) -> dict[str, str]:
    if lang == "en":
        return {"footprints": "Footprints", "tracks": "Tracks", "vias": "Vias", "unconnected": "Unconnected"}
    return {"footprints": "Huellas", "tracks": "Pistas", "vias": "Vías", "unconnected": "Sin conectar"}


def settings_path(lang: str) -> str:
    folder = "~/Library/Application Support/kicad-ia/user-settings.json"
    if lang == "en":
        return f"Saved in {folder}"
    return f"Se guardan en {folder}"


def orden_a_pcb(browser: Browser, work: Path, summary: dict, java: dict, lang: str) -> list[dict]:
    renders = work / "renders"
    written = json.loads((work / "place_circuit.json").read_text(encoding="utf-8"))
    written = {key: written[key] for key in ("ok", "written", "added", "net_stubs", "power_flags", "errors")}
    written["file"] = "led-usbc.kicad_sch"
    written["backup"] = "led-usbc-backups/kicad-ia/led-usbc.kicad_sch"
    stats = summary["stats"]
    sch, _ = cropped(browser, renders / "esquematico.svg")
    placed, _ = cropped(browser, renders / "placa-colocada.svg")
    routed, _ = cropped(browser, renders / "placa-ruteada.svg")
    # Las vistas del editor usan el mismo encuadre que la placa tras F8.
    f8_board, frame = cropped(browser, renders / "placa-f8.svg")
    empty_board, _ = cropped(browser, renders / "placa-vacia.svg", frame)
    view3d = data_url(renders / "placa-3d.png")
    icon = data_url(APP / "icons" / "kicad-ia-light-48.png")
    st = lambda tokens: js_status(status(summary, java, llm=True, autoroute=True, tokens=tokens))  # noqa: E731
    labels = board_labels(lang)
    if lang == "en":
        session_title = "Design an LED with its resistor, powered at 5 V from USB-C."
        user_order = session_title
        question = (
            "I already have the **USB-C** connector (`Connector:USB_C_Receptacle_PowerOnly_6P`) with its footprint. "
            "**R1** and the **LED** have no footprint on the symbol. Your libraries include:\n"
            "- 0603: `R_0603_1608Metric`, `LED_0603_1608Metric`\n"
            "- 0805: `R_0805_2012Metric`, `LED_0805_2012Metric`\n"
            "- THT: `R_Axial_DIN0207…`, `LED_D5.0mm`\n\n"
            "Which package should I use? Also, so a USB-C charger delivers 5 V, I suggest **R2** and **R3** "
            "of 5.1 kΩ from CC1 and CC2 to GND. Should I add them?"
        )
        user_packages = "0805, and yes, add R2 and R3."
        said_schematic = (
            "Schematic written to `led-usbc.kicad_sch`, with a copy in `led-usbc-backups/kicad-ia/`. ERC reports no errors.\\n\\n"
            "Next: in the PCB editor, **Tools → Update PCB from Schematic (F8)**. The board is 32 × 22 mm (outline on Edge.Cuts)."
        )
        user_place = "Place the components to IPC Class 2. Show the proposal first."
        said_place = (
            "Proposal ready, not applied:\\n- **J1** on the left edge.\\n- **R2** and **R3** next to CC1 and CC2.\\n"
            "- **R1** and **D1** in a row, on the right.\\n\\n"
            "IPC Class 2 pre-check with no errors (this is not a certification). The reviewer approved it. Should I apply it?"
        )
        user_route = "Yes, apply it. Then autoroute, and do not apply until I confirm."
        said_route = (
            f"FreeRouting 2.0.1 candidate: {stats['tracks']} tracks, {stats['vias']} vias and {round(stats['track_length_mm'])} mm of copper. "
            f"DRC with no errors and {summary['unconnected']} unrouted nets. The board open in KiCad is unchanged. Should I apply the routing?"
        )
        user_apply = "Apply it. Show me the board in 3D."
        said_apply = "Routing applied on the open board. Here it is in 3D. Review it and save the board in KiCad."
        window_title = "led-usbc — PCB Editor"
    else:
        session_title = "Diseña un LED con su resistencia alimentado a 5 V por USB-C."
        user_order = session_title
        question = (
            "Ya tengo el conector **USB-C** (`Connector:USB_C_Receptacle_PowerOnly_6P`) con su huella. "
            "**R1** y el **LED** no traen huella en el símbolo. En tus bibliotecas hay:\n"
            "- 0603: `R_0603_1608Metric`, `LED_0603_1608Metric`\n"
            "- 0805: `R_0805_2012Metric`, `LED_0805_2012Metric`\n"
            "- THT: `R_Axial_DIN0207…`, `LED_D5.0mm`\n\n"
            "¿Qué encapsulado uso? Además, para que un cargador USB-C entregue 5 V, propongo **R2** y **R3** "
            "de 5,1 kΩ de CC1 y CC2 a GND. ¿Las añado?"
        )
        user_packages = "0805, y sí, añade R2 y R3."
        said_schematic = (
            "Esquemático escrito en `led-usbc.kicad_sch`, con copia en `led-usbc-backups/kicad-ia/`. El ERC no da errores.\\n\\n"
            "Siguiente paso: en el editor de PCB, **Herramientas → Actualizar PCB desde el esquemático (F8)**. La placa mide 32 × 22 mm (contorno en Edge.Cuts)."
        )
        user_place = "Coloca los componentes con IPC Clase 2. Primero la propuesta."
        said_place = (
            "Propuesta lista, sin aplicar:\\n- **J1** en el borde izquierdo.\\n- **R2** y **R3** junto a CC1 y CC2.\\n"
            "- **R1** y **D1** en línea, a la derecha.\\n\\n"
            "Prechequeo IPC Clase 2 sin errores (no es una certificación). El revisor la aprobó. ¿La aplico?"
        )
        user_route = "Sí, aplícala. Después autorutea y no apliques hasta que confirme."
        said_route = (
            f"Candidato de FreeRouting 2.0.1: {stats['tracks']} pistas, {stats['vias']} vías y {round(stats['track_length_mm'])} mm de cobre. "
            f"DRC sin errores y {summary['unconnected']} redes sin rutear. La placa abierta en KiCad todavía no cambia. ¿Aplico el ruteo?"
        )
        user_apply = "Aplica. Enséñame la placa en 3D."
        said_apply = "Ruteo aplicado en la placa abierta. Aquí la tienes en 3D. Revísala y guarda la placa en KiCad."
        window_title = "led-usbc — Editor de PCB"
    session = f"renderSessions([{{id: 's1', title: {json.dumps(session_title, ensure_ascii=False)}}}], 's1');"
    return [
        {
            "id": "boton",
            "kind": "kicad",
            "board": empty_board,
            "icon": icon,
            "title": window_title,
            "status": {labels["footprints"]: 0, labels["tracks"]: 0},
            "marks": ["#plugin"],
            "cursor": True,
        },
        {
            "id": "chat",
            "setup": st(0) + "renderSelection({items: []});",
            "marks": ["document.querySelector('.indicators')", "document.querySelector('#facts').closest('.card')"],
        },
        {
            "id": "orden",
            "setup": st(18420)
            + session
            + f"""
            __turn('t1');
            __user({json.dumps(user_order, ensure_ascii=False)});
            __tool('inspect_context', {{}}, {{ok: true, project: 'led-usbc', board_open: true}});
            __tool('commit_intent', {{goal: {json.dumps(user_order, ensure_ascii=False)}}}, {{ok: true, version: 1}});
            __tool('search_parts', {{query: 'USB-C receptacle'}}, {{ok: true, count: 9}});
            __tool('search_parts', {{query: 'LED'}}, {{ok: true, count: 24}});
            __tool('describe_part', {{lib_id: 'Connector:USB_C_Receptacle_PowerOnly_6P'}});
            """,
            "marks": ["__last('.msg.user')", "__last('.steps')"],
        },
        {
            "id": "pregunta",
            "setup": st(31960)
            + f"""
            __finish(4, 'describe_part', {{lib_id: 'Connector:USB_C_Receptacle_PowerOnly_6P'}}, {{ok: true, pins: 7, footprint: 'Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal'}});
            __tool('select_component', {{lib_id: 'Device:R'}}, {{ok: true, decision: 'footprint_required'}});
            __say({json.dumps(question, ensure_ascii=False)});
            __done();
            """,
            "marks": ["__last('.msg.assistant')"],
        },
        {
            "id": "esquematico",
            "setup": st(88300)
            + f"""
            __turn('t2');
            __user({json.dumps(user_packages, ensure_ascii=False)});
            __tool('select_component', {{lib_id: 'Device:R'}}, {{ok: true, decision: 'selected'}});
            __tool('select_component', {{lib_id: 'Device:LED'}}, {{ok: true, decision: 'selected'}});
            __tool('select_component', {{lib_id: 'Connector:USB_C_Receptacle_PowerOnly_6P'}}, {{ok: true, decision: 'selected'}});
            __tool('place_circuit', {{symbols: [1,2,3,4,5], nets: [1,2,3,4,5]}}, {json.dumps(written, ensure_ascii=False)});
            __tool('sync_board', {{}}, {{ok: true, erc_errors: 0}});
            __tool('render_view', {{view: 'schematic'}}, {{ok: true, image: '{sch}'}});
            __say({json.dumps(said_schematic, ensure_ascii=False)});
            __done();
            """,
            "marks": ["__last('.figure')", "__last('.msg.assistant')"],
        },
        {
            "id": "f8",
            "kind": "kicad",
            "board": f8_board,
            "icon": icon,
            "title": window_title,
            "status": {labels["footprints"]: stats["footprints"], labels["tracks"]: 0},
            "menu": True,
            "marks": ["#f8"],
            "cursor": True,
        },
        {
            "id": "colocacion",
            "setup": st(141200)
            + f"""
            __turn('t3');
            __user({json.dumps(user_place, ensure_ascii=False)});
            __tool('board_state', {{}}, {{ok: true, footprints: 5}});
            __tool('ipc_place_components', {{apply: false}}, {{ok: true, candidate_id: 'place-1', image: '{placed}', review: {{verdict: 'approved'}}}});
            __say({json.dumps(said_place, ensure_ascii=False)});
            __done();
            """,
            "marks": ["__last('.figure')", "__last('.msg.assistant')"],
        },
        {
            "id": "autoruteo",
            "setup": st(197800)
            + f"""
            __turn('t4');
            __user({json.dumps(user_route, ensure_ascii=False)});
            __tool('ipc_place_components', {{apply: true, candidate_id: 'place-1'}}, {{ok: true, applied: true}});
            __tool('autoroute_board', {{apply: false}}, {{ok: true, candidate_id: 'route-1', image: '{routed}', drc_errors: {summary['drc_errors']}, unrouted: {summary['unconnected']}}});
            __say({json.dumps(said_route, ensure_ascii=False)});
            __done();
            """,
            "marks": ["__last('.figure')", "__last('.msg.assistant')"],
        },
        {
            "id": "aplicado",
            "setup": st(236500)
            + f"""
            __turn('t5');
            __user({json.dumps(user_apply, ensure_ascii=False)});
            __tool('autoroute_board', {{apply: true, candidate_id: 'route-1'}}, {{ok: true, applied: true}});
            __tool('render_view', {{view: 'pcb_3d_iso'}}, {{ok: true, image: '{view3d}'}});
            __say({json.dumps(said_apply, ensure_ascii=False)});
            __done();
            """,
            "marks": ["__last('.figure')", "__last('.msg.assistant')"],
        },
        {
            "id": "kicad-final",
            "kind": "kicad",
            "board": routed,
            "icon": icon,
            "title": window_title,
            "status": {
                labels["footprints"]: stats["footprints"],
                labels["tracks"]: stats["tracks"],
                labels["vias"]: stats["vias"],
                labels["unconnected"]: summary["unconnected"],
            },
        },
    ]


def configuracion(summary: dict, java: dict) -> list[dict]:
    off = js_status(status(summary, java, llm=False, autoroute=False, tokens=0))
    ready = js_status(status(summary, java, llm=True, autoroute=True, tokens=0))
    return [
        {
            "id": "sin-modelo",
            "setup": off + "renderSelection({items: []}); refreshComposer();",
            "marks": ["document.getElementById('ind-model')", "document.getElementById('open-settings')", "document.getElementById('hint')"],
            "cursor": 1,
        },
        {
            "id": "proveedor",
            "setup": """
            openSettings();
            await new Promise((ok) => setTimeout(ok, 600));
            __neutral();
            const preset = document.getElementById('set-preset');
            preset.value = 'gemini';
            preset.dispatchEvent(new Event('change'));
            document.getElementById('set-preset').scrollIntoView({block: 'start'});
            """,
            "marks": ["[__lbl('set-preset'), __lbl('set-base-url')]"],
        },
        {
            "id": "api-key",
            "setup": """
            const key = document.getElementById('set-api-key');
            key.value = 'AIzaSy-clave-de-ejemplo-0000000000';
            key.focus();
            """,
            "marks": ["[__lbl('set-api-key'), document.getElementById('set-api-hint')]"],
        },
        {
            "id": "modelos",
            "setup": "document.getElementById('set-api-key').blur(); __lbl('set-review-model').scrollIntoView({block: 'center'});",
            "marks": ["[__lbl('set-model'), __lbl('set-review-model')]"],
        },
        {
            "id": "java",
            "setup": """
            document.getElementById('set-java').closest('section').scrollIntoView({block: 'center'});
            document.getElementById('set-java-detect').click();
            await new Promise((ok) => setTimeout(ok, 1500));
            __neutral();
            """,
            "marks": ["document.getElementById('set-java').closest('section')"],
            "cursor": 0,
        },
        {
            "id": "autoruteo",
            "setup": """
            const box = document.getElementById('set-autoroute');
            box.checked = true;
            box.dispatchEvent(new Event('change'));
            const values = {'fab-track': 0.25, 'fab-clearance': 0.2, 'fab-via-dia': 0.6, 'fab-via-drill': 0.3, 'fab-hole': 0.3};
            for (const [id, value] of Object.entries(values)) document.getElementById(id).value = value;
            box.closest('section').scrollIntoView({block: 'center'});
            """,
            "marks": ["document.getElementById('set-autoroute').closest('section')"],
        },
        {
            "id": "guardar",
            "setup": "__neutral(); document.querySelector('.modal-foot').scrollIntoView({block: 'end'});",
            "marks": ["document.getElementById('settings-path')", "document.querySelector('.modal-foot .primary')"],
            "cursor": 1,
        },
        {
            "id": "listo",
            "setup": "closeSettings();"
            + ready
            + """
            els.quickMenu.hidden = false;
            els.quickActions.setAttribute('aria-expanded', 'true');
            """,
            "marks": [
                "document.getElementById('ind-model')",
                "document.querySelector('#facts').closest('.card')",
                "document.getElementById('btn-autoroute')",
            ],
            "cursor": 2,
        },
    ]


def start_server(work: Path, port: int) -> subprocess.Popen:
    env = {
        **os.environ,
        "KICAD_MODE": "fake",
        "KICAD_IA_CONFIG": str(work / "config"),
        "KICAD_IA_CACHE": str(work / "cache"),
        "PORT": str(port),
        "PYTHONPATH": str(APP / "src"),
    }
    for key in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_REVIEW_MODEL", "AUTOROUTE_ENABLED"):
        env.pop(key, None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "kicad_ia"],
        cwd=work,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
            return proc
        except Exception:
            time.sleep(0.25)
    proc.terminate()
    raise SystemExit("El chat no arrancó.")


def capture_chat(browser: Browser, url: str, scenes: list[dict], shots: Path, lang: str) -> None:
    browser.viewport(CHAT_W, CHAT_H, 2)
    browser.call(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": f"localStorage.setItem('kicad-ia-lang', {json.dumps(lang)});"},
    )
    browser.goto(url)
    browser.wait(
        f"document.documentElement.lang === {json.dumps(lang)} && document.getElementById('ind-ws').classList.contains('ok')"
    )
    time.sleep(0.8)
    browser.js(HELPERS.replace("__JAVA__", JAVA_SHOWN).replace("__PATH__", settings_path(lang)))
    browser.js("document.querySelector('.coffee')?.remove(); true")
    for scene in scenes:
        if scene.get("kind") == "kicad":
            continue
        browser.js(f"(async () => {{ {scene['setup']} ; return true; }})()")
        time.sleep(0.6)
        browser.js("document.querySelectorAll('img').length; scrollDown(); true")
        time.sleep(0.4)
        scene["marks_px"] = [browser.js(f"__rect({expression})") for expression in scene["marks"]]
        path = shots / f"{scene['id']}.png"
        browser.shoot(path)
        scene["image"] = data_url(path)


def compose(browser: Browser, tour: str, scenes: list[dict], frames: Path, lang: str) -> None:
    browser.viewport(1920, 1080, 1)
    browser.goto((HERE / "escenario.html").as_uri())
    target = OUT / tour / lang
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.webp"):
        old.unlink()
    title = "led-usbc — PCB Editor" if lang == "en" else "led-usbc — Editor de PCB"
    for number, scene in enumerate(scenes, start=1):
        payload = {key: value for key, value in scene.items() if key not in ("setup",)}
        if payload.get("kind") != "kicad":
            payload["marks"] = [mark for mark in scene.get("marks_px", []) if mark]
        payload.setdefault("title", title)
        payload["lang"] = lang
        browser.js(f"render({json.dumps(payload)})")
        time.sleep(0.25)
        name = f"{number:02d}-{scene['id']}"
        browser.shoot(frames / tour / f"{name}.png")
        browser.shoot(target / f"{name}.webp", fmt="webp", quality=82)
        print(tour, name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("/tmp/kicad-ia-recorrido"))
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--chrome", type=int, default=9335)
    parser.add_argument("--lang", choices=("es", "en"), default="es")
    args = parser.parse_args()
    work = args.dir
    summary = json.loads((work / "resumen.json").read_text(encoding="utf-8"))
    from kicad_ia.kicad.freerouting import probe_java

    probe = probe_java()
    java = {"ok": bool(probe.get("ok")), "label": probe.get("label") or "Java 17+"}

    server = start_server(work, args.port)
    browser = Browser(args.chrome)
    try:
        browser.goto("about:blank")
        tours = {
            "de-la-orden-a-la-pcb": orden_a_pcb(browser, work, summary, java, args.lang),
            "configuracion-inicial": configuracion(summary, java),
        }
        for tour, scenes in tours.items():
            shots = work / "capturas" / args.lang / tour
            shots.mkdir(parents=True, exist_ok=True)
            capture_chat(browser, f"http://127.0.0.1:{args.port}/", scenes, shots, args.lang)
        for tour, scenes in tours.items():
            compose(browser, tour, scenes, work / "fotogramas" / args.lang, args.lang)
    finally:
        browser.close()
        server.terminate()


if __name__ == "__main__":
    main()
