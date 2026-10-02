from kicad_ia.agent.loop import Session
from kicad_ia.agent.sessions import SessionStore


def test_sessions_save_reload_and_list(tmp_path):
    store = SessionStore(tmp_path)
    session = Session("abc123")
    session.messages.append({"role": "user", "content": "un LED con USB"})
    session.memory.commit({"goal": "led", "required_components": ["LED"]})
    assert store.save(session) is True
    loaded = store.load("abc123")
    assert loaded.title == "un LED con USB"
    assert loaded.memory.contract.required_components == ["LED"]
    assert loaded.messages[0]["content"] == "un LED con USB"
    assert store.summaries()[0]["id"] == "abc123"
    assert store.delete("abc123") is True
    assert store.load("abc123") is None


def test_empty_session_is_not_saved(tmp_path):
    store = SessionStore(tmp_path)
    assert store.save(Session("vacio")) is False
    assert store.summaries() == []
