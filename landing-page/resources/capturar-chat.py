#!/usr/bin/env python3
"""Captura el chat, el menú de acciones y Ajustes para la landing.

Necesita el chat ya en marcha (el botón KiCad IA, o `python -m kicad_ia`)
y Google Chrome. No guarda la API key: vacía el campo antes de la foto
y no pulsa Guardar.

Para que la barra lateral muestre conversaciones sin usar las tuyas, arranca
un chat aparte con un directorio de ajustes propio y siembra ejemplos:

  python3 resources/capturar-chat.py --seed /tmp/kicad-ia-captura-config
  KICAD_IA_CONFIG=/tmp/kicad-ia-captura-config PORT=8766 python -m kicad_ia
  python3 resources/capturar-chat.py --url http://127.0.0.1:8766/

Uso normal, desde landing-page/:
  python3 resources/capturar-chat.py
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "media"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765/")
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--seed", type=Path, help="escribe conversaciones de ejemplo en DIR/sessions y sale")
    args = parser.parse_args()
    if args.seed:
        seed_sessions(args.seed)
        return

    import websockets.sync.client as wsclient

    user_data = Path("/tmp/kicad-ia-captura")
    user_data.mkdir(exist_ok=True)
    proc = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={args.port}",
            f"--user-data-dir={user_data}",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-extensions",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        sock = wsclient.connect(_debugger(args.port), max_size=32_000_000, legacy=True)
        session = Session(sock)
        session.call("Page.enable")
        session.call("Runtime.enable")
        session.call(
            "Emulation.setEmulatedMedia",
            {"features": [{"name": "prefers-color-scheme", "value": "light"}]},
        )
        session.call("Page.navigate", {"url": args.url})
        session.wait("document.body.innerText.includes('KiCad')")
        time.sleep(0.4)
        session.shoot(OUT / "chat-inicio.png", 1280, 1120)
        session.js("document.getElementById('quick-actions').click()")
        session.wait("!document.getElementById('quick-menu').hidden")
        session.shoot(OUT / "chat-acciones.png", 1280, 1120)
        session.js("document.body.click()")
        session.js("document.getElementById('open-settings').click()")
        session.wait("!document.getElementById('settings-modal').hidden")
        session.wait("document.getElementById('settings-path').textContent.length > 0")
        session.js(
            """
            (() => {
              const key = document.getElementById('set-api-key');
              key.value = '';
              key.placeholder = 'Se guarda en este equipo';
              document.getElementById('set-api-hint').textContent =
                'Gemini y OpenAI necesitan API key. Ollama puede ir vacío.';
              document.getElementById('settings-path').textContent =
                'Se guardan en ~/Library/Application Support/kicad-ia/user-settings.json';
              return 'ok';
            })()
            """
        )
        time.sleep(0.3)
        height = int(
            session.js(
                "Math.ceil(document.querySelector('.modal-panel').getBoundingClientRect().height + 100)"
            )
        )
        session.shoot(OUT / "chat-ajustes.png", 1100, max(980, height))
        sock.close()
    finally:
        proc.terminate()


DEMO_SESSIONS = [
    ("Diseña un LED con su resistencia alimentado a 5 V por USB-C", "2026-10-01T20:40:00+00:00"),
    ("Regulador de 3,3 V para un ESP32 desde 5 V", "2026-10-01T18:05:00+00:00"),
    ("Organiza el circuito por funciones", "2026-09-30T22:15:00+00:00"),
]


def seed_sessions(config_dir: Path) -> None:
    root = config_dir / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    for index, (title, updated) in enumerate(DEMO_SESSIONS, start=1):
        session_id = f"demo{index}"
        payload = {
            "id": session_id,
            "title": title,
            "updated": updated,
            "messages": [{"role": "user", "content": title}],
            "memory": {},
        }
        (root / f"{session_id}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("conversaciones de ejemplo en", root)


def _debugger(port: int) -> str:
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as res:
                tabs = json.load(res)
            for tab in tabs:
                if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                    return tab["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.15)
    raise SystemExit("Chrome no abrió el depurador.")


class Session:
    def __init__(self, sock) -> None:
        self.sock = sock
        self.mid = 0

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 10):
        self.mid += 1
        mine = self.mid
        self.sock.send(json.dumps({"id": mine, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = json.loads(self.sock.recv(timeout=max(0.2, deadline - time.time())))
            if data.get("id") == mine:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result", {})
        raise TimeoutError(method)

    def js(self, expression: str):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        return result.get("result", {}).get("value")

    def wait(self, expression: str, seconds: float = 8) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.js(expression):
                return
            time.sleep(0.25)
        raise SystemExit(f"No apareció: {expression}")

    def shoot(self, path: Path, width: int, height: int) -> None:
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
        )
        time.sleep(0.35)
        shot = self.call("Page.captureScreenshot", {"format": "png"})
        path.write_bytes(base64.b64decode(shot["data"]))
        print(path.name, width, height)


if __name__ == "__main__":
    main()
