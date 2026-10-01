"""Configuración del proceso.

Orden de carga:
1. `.env` en el cwd (solo `setdefault`: no pisa variables ya exportadas).
2. Preferencias de usuario (`user_prefs.py`) si existe el JSON de Ajustes.

No hay secretos en el repositorio: API keys viven en `.env` o en Ajustes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from kicad_ia.user_prefs import DEFAULT_FAB, load_prefs, prefs_path


def _load_env_file() -> None:
    path = Path.cwd() / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    kicad_mode: str = "auto"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_review_model: str = ""
    host: str = "127.0.0.1"
    port: int = 8765
    kicad_cli: str = ""
    watch_interval: float = 1.5
    ipc_class: str = "2"
    freerouting_jar: str = ""
    freerouting_timeout_s: int = 300
    freerouting_download: bool = True
    kicad_python: str = ""
    java_bin: str = ""
    autoroute_enabled: bool = False
    fab: dict = field(default_factory=lambda: dict(DEFAULT_FAB))

    @classmethod
    def from_env(cls, apply_user_prefs: bool = True) -> Settings:
        _load_env_file()
        settings = cls(
            kicad_mode=os.environ.get("KICAD_MODE", "auto").strip().lower() or "auto",
            llm_base_url=os.environ.get("LLM_BASE_URL", "").strip().rstrip("/"),
            llm_api_key=os.environ.get("LLM_API_KEY", "").strip(),
            llm_model=os.environ.get("LLM_MODEL", "").strip(),
            llm_review_model=os.environ.get("LLM_REVIEW_MODEL", "").strip(),
            host=os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=int(os.environ.get("PORT", "8765")),
            kicad_cli=os.environ.get("KICAD_CLI", "").strip(),
            watch_interval=max(0.3, float(os.environ.get("WATCH_INTERVAL", "1.5") or 1.5)),
            ipc_class=os.environ.get("IPC_CLASS", "2").strip() or "2",
            freerouting_jar=os.environ.get("FREEROUTING_JAR", "").strip(),
            freerouting_timeout_s=max(30, int(os.environ.get("FREEROUTING_TIMEOUT", "300") or 300)),
            freerouting_download=os.environ.get("FREEROUTING_DOWNLOAD", "1").strip().lower()
            not in {"0", "false", "no"},
            kicad_python=os.environ.get("KICAD_PYTHON", "").strip(),
            java_bin=os.environ.get("JAVA_BIN", "").strip(),
            autoroute_enabled=os.environ.get("AUTOROUTE_ENABLED", "0").strip().lower()
            in {"1", "true", "yes"},
            fab=dict(DEFAULT_FAB),
        )
        if apply_user_prefs and prefs_path().is_file():
            settings.apply_prefs(load_prefs())
        return settings

    def apply_prefs(self, prefs: dict) -> Settings:
        """Aplica preferencias de usuario (tienen prioridad sobre .env para LLM/Java/autoruteo)."""
        if "llm_base_url" in prefs:
            self.llm_base_url = str(prefs.get("llm_base_url") or "").strip().rstrip("/")
        if "llm_api_key" in prefs:
            key = str(prefs.get("llm_api_key") or "").strip()
            if key:
                self.llm_api_key = key
            elif prefs.get("_clear_api_key"):
                self.llm_api_key = ""
        if "llm_model" in prefs:
            self.llm_model = str(prefs.get("llm_model") or "").strip()
        if "llm_review_model" in prefs:
            self.llm_review_model = str(prefs.get("llm_review_model") or "").strip()
        if "java_bin" in prefs:
            self.java_bin = str(prefs.get("java_bin") or "").strip()
        if "autoroute_enabled" in prefs:
            self.autoroute_enabled = bool(prefs.get("autoroute_enabled"))
        if isinstance(prefs.get("fab"), dict):
            fab = dict(DEFAULT_FAB)
            for key in DEFAULT_FAB:
                if key in prefs["fab"]:
                    try:
                        fab[key] = float(prefs["fab"][key])
                    except (TypeError, ValueError):
                        pass
            self.fab = fab
        return self

    def copy(self) -> Settings:
        return replace(self, fab=dict(self.fab))

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def fab_summary(self) -> dict:
        return dict(self.fab)
