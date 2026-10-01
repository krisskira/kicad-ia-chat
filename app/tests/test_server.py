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

    chat = client.post("/api/chat", json={"message": "/estado"})
    assert chat.status_code == 200
    body = chat.json()
    assert "Backend: fake" in body["reply"]

    missing = client.post("/api/chat", json={"message": "crea un divisor", "session_id": body["session_id"]})
    assert "Ajustes" in missing.json()["reply"] or "LLM_BASE_URL" in missing.json()["reply"]
