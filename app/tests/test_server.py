from fastapi.testclient import TestClient

from kicad_ia.config import Settings
from kicad_ia.kicad.fake import FakeGateway
from kicad_ia.server.app import create_app


def test_status_and_prompt_flow():
    gateway = FakeGateway()
    app = create_app(Settings(kicad_mode="fake"), gateway)
    client = TestClient(app)
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["capabilities"]["backend"] == "fake"
    assert status.json()["llm_ready"] is False

    page = client.get("/")
    assert page.status_code == 200
    assert "KiCad IA" in page.text

    page_text = page.text
    assert 'id="lang-switch"' in page_text
    assert 'data-set-lang="en"' in page_text
    assert 'data-set-lang="es"' in page_text
    assert "What should we design?" in page_text

    chat = client.post("/api/chat", json={"message": "/status"})
    assert chat.status_code == 200
    body = chat.json()
    assert "Backend: fake" in body["reply"]
    assert "Schematic:" in body["reply"]

    spanish = client.post("/api/chat", json={"message": "/estado", "lang": "es"})
    assert "Esquemático:" in spanish.json()["reply"]

    missing = client.post("/api/chat", json={"message": "crea un divisor", "session_id": body["session_id"]})
    assert "Settings" in missing.json()["reply"]
    assert "LLM_BASE_URL" in missing.json()["reply"]

    missing_es = client.post(
        "/api/chat", json={"message": "crea un divisor", "session_id": spanish.json()["session_id"], "lang": "es"}
    )
    assert "Ajustes" in missing_es.json()["reply"]
