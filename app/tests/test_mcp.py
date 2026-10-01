"""Pruebas del servidor MCP (list/call de herramientas)."""

from __future__ import annotations

import json

import pytest
from mcp import types

from kicad_ia.config import Settings
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.kicad.serialized import SerializedGateway
from kicad_ia.mcp import build_server, excluded_tools
from kicad_ia.tools.registry import build_registry

pytest.importorskip("mcp")
pytest.importorskip("pytest_asyncio", reason="pytest-asyncio para tests async del MCP")


@pytest.mark.asyncio
async def test_mcp_lists_and_calls_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    settings = Settings(kicad_mode="fake", autoroute_enabled=False)
    gateway = SerializedGateway(FakeGateway())
    registry = build_registry()
    server = build_server(settings, gateway, registry)

    assert "autoroute_board" in excluded_tools(settings)

    list_handler = server.request_handlers[types.ListToolsRequest]
    listed = await list_handler(types.ListToolsRequest(method="tools/list", params=None))
    names = {tool.name for tool in listed.root.tools}
    assert "inspect_context" in names
    assert "place_circuit" in names
    assert "autoroute_board" not in names

    call_handler = server.request_handlers[types.CallToolRequest]
    called = await call_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="inspect_context", arguments={}),
        )
    )
    payload = json.loads(called.root.content[0].text)
    assert payload["ok"] is True
    assert payload["capabilities"]["backend"] == "fake"


@pytest.mark.asyncio
async def test_mcp_includes_autoroute_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_IA_CONFIG", str(tmp_path))
    settings = Settings(kicad_mode="fake", autoroute_enabled=True)
    server = build_server(settings, SerializedGateway(FakeGateway()), build_registry())
    list_handler = server.request_handlers[types.ListToolsRequest]
    listed = await list_handler(types.ListToolsRequest(method="tools/list", params=None))
    names = {tool.name for tool in listed.root.tools}
    assert "autoroute_board" in names
