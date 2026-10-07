"""Ajustes del usuario (LLM, Java, autoruteo, fabricación).

Persisten fuera del `.env` para poder cambiarlos desde la UI ⚙ sin reiniciar
a mano el archivo de entorno. Rutas típicas:
- macOS: ~/Library/Application Support/kicad-ia/user-settings.json
- Linux: ~/.config/kicad-ia/user-settings.json
- Override: KICAD_IA_CONFIG
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PREFS_NAME = "user-settings.json"

DEFAULT_FAB = {
    "min_track_mm": 0.15,
    "min_clearance_mm": 0.15,
    "min_via_diameter_mm": 0.6,
    "min_via_drill_mm": 0.3,
    "min_hole_mm": 0.3,
}

# Solo rellenan el formulario. El chat habla siempre con /chat/completions
# compatible con OpenAI (Gemini, Ollama, OpenAI o cualquier proxy).
LLM_PRESETS = [
    {
        "id": "gemini",
        "label": "Google Gemini",
        "llm_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "llm_model": "gemini-2.5-flash",
        "llm_review_model": "",
        "model_placeholder": "gemini-2.5-flash",
        "needs_key": True,
        "key_hint": "Este proveedor pide API key.",
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "llm_base_url": "http://127.0.0.1:11434/v1",
        "llm_model": "qwen2.5-coder",
        "llm_review_model": "",
        "model_placeholder": "qwen2.5-coder",
        "needs_key": False,
        "key_hint": "Ollama no necesita API key.",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4o-mini",
        "llm_review_model": "",
        "model_placeholder": "gpt-4o-mini",
        "needs_key": True,
        "key_hint": "Este proveedor pide API key.",
    },
    {
        "id": "custom",
        "label": "Compatible con OpenAI (personalizado)",
        "llm_base_url": "",
        "llm_model": "",
        "llm_review_model": "",
        "model_placeholder": "nombre-del-modelo",
        "needs_key": True,
        "key_hint": "Si el servidor lo exige, pon la API key. Si no, déjala vacía.",
    },
]


def prefs_dir() -> Path:
    configured = os.environ.get("KICAD_IA_CONFIG", "").strip()
    if configured:
        root = Path(configured)
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "kicad-ia"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kicad-ia"
    root.mkdir(parents=True, exist_ok=True)
    return root


def prefs_path() -> Path:
    return prefs_dir() / PREFS_NAME


def default_prefs() -> dict:
    return {
        "llm_base_url": "",
        "llm_api_key": "",
        "llm_model": "",
        "llm_review_model": "",
        "java_bin": "",
        "autoroute_enabled": False,
        "fab": dict(DEFAULT_FAB),
    }


def load_prefs() -> dict:
    path = prefs_path()
    base = default_prefs()
    if not path.is_file():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if not isinstance(data, dict):
        return base
    merged = {**base, **{k: data[k] for k in base if k in data and k != "fab"}}
    fab = dict(DEFAULT_FAB)
    raw_fab = data.get("fab") if isinstance(data.get("fab"), dict) else {}
    for key in DEFAULT_FAB:
        if key in raw_fab:
            try:
                fab[key] = float(raw_fab[key])
            except (TypeError, ValueError):
                pass
    merged["fab"] = fab
    merged["autoroute_enabled"] = bool(merged.get("autoroute_enabled"))
    for key in ("llm_base_url", "llm_api_key", "llm_model", "llm_review_model", "java_bin"):
        merged[key] = str(merged.get(key) or "").strip()
    return merged


def save_prefs(data: dict) -> dict:
    cleaned = validate_and_normalize(data)
    path = prefs_path()
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cleaned


def validate_and_normalize(data: dict) -> dict:
    out = default_prefs()
    if not isinstance(data, dict):
        raise ValueError("El cuerpo de ajustes debe ser un objeto JSON.")
    out["llm_base_url"] = str(data.get("llm_base_url") or "").strip().rstrip("/")
    out["llm_api_key"] = str(data.get("llm_api_key") or "").strip()
    out["llm_model"] = str(data.get("llm_model") or "").strip()
    out["llm_review_model"] = str(data.get("llm_review_model") or "").strip()
    out["java_bin"] = str(data.get("java_bin") or "").strip()
    out["autoroute_enabled"] = bool(data.get("autoroute_enabled"))
    fab_in = data.get("fab") if isinstance(data.get("fab"), dict) else {}
    fab = dict(DEFAULT_FAB)
    for key in DEFAULT_FAB:
        if key in fab_in and fab_in[key] not in (None, ""):
            fab[key] = float(fab_in[key])
            if fab[key] <= 0:
                raise ValueError(f"fab.{key} debe ser mayor que 0.")
    out["fab"] = fab
    if out["autoroute_enabled"]:
        missing = [k for k, v in fab.items() if v <= 0]
        if missing:
            raise ValueError("Con el autoruteo activo hay que indicar anchos y taladros de fabricación.")
        if fab["min_via_drill_mm"] >= fab["min_via_diameter_mm"]:
            raise ValueError("El taladro de vía debe ser menor que el diámetro de la vía.")
        if fab["min_hole_mm"] > fab["min_via_drill_mm"] * 1.5 and fab["min_hole_mm"] > fab["min_via_drill_mm"]:
            # solo aviso lógico suave: hole can equal via drill
            pass
    if out["java_bin"] and not Path(out["java_bin"]).is_file():
        raise ValueError(f"No existe el ejecutable de Java: {out['java_bin']}")
    return out


def public_prefs(prefs: dict) -> dict:
    """Vista segura para la UI (API key enmascarada)."""
    key = str(prefs.get("llm_api_key") or "")
    masked = ""
    if key:
        masked = ("*" * max(0, len(key) - 4)) + key[-4:]
    return {
        **prefs,
        "llm_api_key": "",
        "llm_api_key_set": bool(key),
        "llm_api_key_masked": masked,
        "presets": LLM_PRESETS,
        "path": str(prefs_path()),
    }
