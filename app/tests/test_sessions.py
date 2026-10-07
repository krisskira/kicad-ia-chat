from kicad_ia.agent.loop import Session
from kicad_ia.agent.sessions import SessionStore


def test_sessions_save_reload_and_list(tmp_path):
    store = SessionStore(tmp_path)
    session = Session("abc123")
    session.messages.append({"role": "user", "content": "un LED con USB"})
    session.memory.commit({"goal": "led", "required_components": ["LED"]})
    session.usage_log.append({"round": 1, "role": "main", "prompt": 10, "completion": 2, "total": 12})
    assert store.save(session) is True
    loaded = store.load("abc123")
    assert loaded.title == "un LED con USB"
    assert loaded.memory.contract.required_components == ["LED"]
    assert loaded.messages[0]["content"] == "un LED con USB"
    assert loaded.usage_log[0]["role"] == "main"
    assert store.summaries()[0]["id"] == "abc123"
    assert store.delete("abc123") is True
    assert store.load("abc123") is None


def test_old_session_without_usage_log_loads(tmp_path):
    path = tmp_path / "vieja.json"
    path.write_text(
        '{"id":"vieja","title":"hola","updated":"2026-01-01T00:00:00+00:00","project":"","messages":[{"role":"user","content":"hola"}],"memory":{}}',
        encoding="utf-8",
    )
    loaded = SessionStore(tmp_path).load("vieja")
    assert loaded is not None
    assert loaded.usage_log == []


def test_summaries_stay_inside_one_project(tmp_path):
    store = SessionStore(tmp_path)
    first = Session("uno", project="/placas/alfa")
    first.messages.append({"role": "user", "content": "un LED"})
    first.messages.append({"role": "assistant", "content": "Quedó U1 con huella 0603."})
    other = Session("dos", project="/placas/beta")
    other.messages.append({"role": "user", "content": "un regulador"})
    assert store.save(first) and store.save(other)
    assert [row["id"] for row in store.summaries("/placas/alfa")] == ["uno"]
    text = store.digest("/placas/alfa", exclude="otra")
    assert "un LED" in text and "0603" in text
    assert "regulador" not in text
    assert store.digest("/placas/alfa", exclude="uno") == ""


def test_empty_session_is_not_saved(tmp_path):
    store = SessionStore(tmp_path)
    assert store.save(Session("vacio")) is False
    assert store.summaries() == []
