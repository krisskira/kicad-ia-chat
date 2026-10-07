"""Chrome headless por el protocolo de depuración. Solo lo que usan los recorridos."""

from __future__ import annotations

import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

import websockets.sync.client as wsclient

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class Browser:
    def __init__(self, port: int = 9334) -> None:
        profile = Path("/tmp/kicad-ia-recorrido-chrome")
        profile.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}",
                "--hide-scrollbars",
                "--no-first-run",
                "--disable-extensions",
                "--allow-file-access-from-files",
                "--force-color-profile=srgb",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.sock = wsclient.connect(_debugger(port), max_size=64_000_000)
        self.mid = 0
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})

    def close(self) -> None:
        try:
            self.sock.close()
        finally:
            self.proc.terminate()

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 30):
        self.mid += 1
        mine = self.mid
        self.sock.send(json.dumps({"id": mine, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = json.loads(self.sock.recv(timeout=max(0.2, deadline - time.time())))
            if data.get("id") == mine:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})
        raise TimeoutError(method)

    def js(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description") or result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression: str, seconds: float = 10) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.js(expression):
                return
            time.sleep(0.2)
        raise SystemExit(f"No apareció: {expression}")

    def viewport(self, width: int, height: int, scale: float = 1) -> None:
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {"width": width, "height": height, "deviceScaleFactor": scale, "mobile": False},
        )

    def goto(self, url: str) -> None:
        self.call("Page.navigate", {"url": url})
        time.sleep(0.3)
        self.wait("document.readyState === 'complete'")

    def shoot(self, path: Path, fmt: str = "png", quality: int = 88) -> None:
        params = {"format": fmt}
        if fmt in ("jpeg", "webp"):
            params["quality"] = quality
        shot = self.call("Page.captureScreenshot", params)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(shot["data"]))


def _debugger(port: int) -> str:
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as res:
                tabs = json.load(res)
            for tab in tabs:
                if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                    return tab["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.15)
    raise SystemExit("Chrome no abrió el depurador.")


def data_url(path: Path) -> str:
    kind = {".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp"}[path.suffix]
    return f"data:{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"
