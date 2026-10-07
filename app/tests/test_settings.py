"""Pruebas de ajustes de usuario, detección de Java y API de settings."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kicad_ia.config import Settings
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.freerouting import find_java, probe_java
from kicad_ia.server.app import create_app
from kicad_ia.tools.registry import build_registry
from kicad_ia.user_prefs import DEFAULT_FAB, load_prefs, save_prefs, validate_and_normalize


def test_validate_fab_requires_via_drill_smaller(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    bad = {
        "autoroute_enabled": True,
        "fab": {**DEFAULT_FAB, "min_via_drill_mm": 1.0, "min_via_diameter_mm": 0.6},
    }
    try:
        validate_and_normalize(bad)
        assert False, "debía fallar"
    except ValueError as exc:
        assert "taladro" in str(exc).lower()


def test_save_and_load_prefs(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    saved = save_prefs(
        {
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen",
            "llm_api_key": "",
            "autoroute_enabled": True,
            "fab": DEFAULT_FAB,
            "java_bin": "",
        }
    )
    assert saved["autoroute_enabled"] is True
    loaded = load_prefs()
    assert loaded["llm_model"] == "qwen"
    assert loaded["fab"]["min_track_mm"] == DEFAULT_FAB["min_track_mm"]


def test_settings_apply_prefs_overrides_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    monkeypatch.setenv("LLM_BASE_URL", "http://env-default/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    settings = Settings.from_env(apply_user_prefs=False)
    assert settings.llm_model == "env-model"
    settings.apply_prefs({"llm_base_url": "http://ui/v1", "llm_model": "ui-model", "autoroute_enabled": True, "fab": DEFAULT_FAB})
    assert settings.llm_model == "ui-model"
    assert settings.autoroute_enabled is True


def test_probe_java_returns_structure():
    result = probe_java()
    assert "ok" in result
    if result["ok"]:
        assert Path(result["java"]).is_file()
        assert result["major"] >= 1
    else:
        assert result.get("error")


def test_find_java_respects_configured(tmp_path):
    fake = tmp_path / "java"
    fake.write_text("#!/bin/sh\necho version \\\"21.0.0\\\" >&2\n", encoding="utf-8")
    fake.chmod(0o755)
    # find_java only checks is_file + executable; version is separate
    found = find_java(str(fake))
    assert found == str(fake)


def test_api_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    settings = Settings.from_env(apply_user_prefs=False)
    settings.kicad_mode = "fake"
    app = create_app(settings, FakeGateway(), watch=False)
    client = TestClient(app)

    got = client.get("/api/settings")
    assert got.status_code == 200
    body = got.json()
    assert "presets" in body
    assert body["autoroute_enabled"] is False

    put = client.put(
        "/api/settings",
        json={
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen2.5-coder",
            "llm_api_key": "secret-key-1234",
            "keep_api_key": False,
            "autoroute_enabled": True,
            "fab": DEFAULT_FAB,
            "java_bin": "",
        },
    )
    assert put.status_code == 200, put.text
    saved = put.json()
    assert saved["llm_model"] == "qwen2.5-coder"
    assert saved["llm_api_key_set"] is True
    assert saved["autoroute_enabled"] is True
    assert "secret" not in saved.get("llm_api_key", "")

    tools = client.get("/api/tools").json()["tools"]
    assert "autoroute_board" in tools

    status = client.get("/api/status").json()
    assert status["llm_ready"] is True
    assert status["autoroute_enabled"] is True


def test_presets_are_openai_compatible_and_review_is_optional():
    """Los presets solo rellenan URL y modelo. Ninguno exige revisor ni un SDK propio."""
    from kicad_ia.user_prefs import LLM_PRESETS

    ids = {row["id"] for row in LLM_PRESETS}
    assert ids == {"gemini", "ollama", "openai", "custom"}
    for row in LLM_PRESETS:
        assert row["llm_review_model"] == ""
        if row["id"] != "custom":
            assert row["llm_base_url"].rstrip("/").endswith("/openai") or row["llm_base_url"].rstrip("/").endswith("/v1")
        assert "needs_key" in row
        assert "key_hint" in row


def test_registry_excludes_autoroute():
    registry = build_registry()
    names = registry.names(exclude={"autoroute_board"})
    assert "autoroute_board" not in names
    blocked = registry.call("autoroute_board", {}, FakeGateway(), exclude={"autoroute_board"})
    assert blocked["ok"] is False
