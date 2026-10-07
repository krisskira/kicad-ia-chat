"""Textos que el chat enseña al usuario, en inglés (por defecto) y español."""

from __future__ import annotations

LANGS = ("en", "es")

STRINGS: dict[str, dict[str, str]] = {
    "reply_language": {"en": "inglés", "es": "español"},
    "empty": {
        "en": "Say what you want to do on the schematic or the board.",
        "es": "Escribe qué quieres hacer en el esquemático o en la placa.",
    },
    "missing_model": {
        "en": (
            "The tool chat is ready, but the model is missing. Open Settings (API key, URL, and model) "
            "or set LLM_BASE_URL and LLM_MODEL in app/.env. Until then you can use /status, /selection, and /tools."
        ),
        "es": (
            "El chat de herramientas está listo, pero falta el modelo. Ábrelo en Ajustes (API key, URL y modelo) "
            "o define LLM_BASE_URL y LLM_MODEL en app/.env. Mientras tanto puedes usar /estado, /seleccion y /herramientas."
        ),
    },
    "tools": {"en": "Tools: {names}.", "es": "Herramientas: {names}."},
    "nothing_selected": {
        "en": "Nothing is selected in the editor.",
        "es": "No hay nada seleccionado en el editor.",
    },
    "selection": {"en": "Selection: {items}.", "es": "Selección: {items}."},
    "item": {"en": "item", "es": "ítem"},
    "inspect": {
        "en": "{selected} Schematic: {symbols} symbols. Board: {footprints} footprints. Backend: {backend}.",
        "es": "{selected} Esquemático: {symbols} símbolos. Placa: {footprints} huellas. Backend: {backend}.",
    },
    "model_failed": {
        "en": "The model did not respond: {error}",
        "es": "El modelo no respondió: {error}",
    },
    "round_limit": {
        "en": "I stopped after several tools so the session would not spin. Review the steps and tell me how to continue.",
        "es": "Paré después de varias herramientas para no dejar la sesión dando vueltas. Revisa los pasos y dime cómo seguir.",
    },
    "done": {"en": "Done.", "es": "Listo."},
    "busy": {
        "en": "Still working on the previous message. Wait until it finishes, or cancel it.",
        "es": "Todavía estoy con el mensaje anterior. Espera a que termine, o cancélalo.",
    },
    "cancelled": {
        "en": "Stopped. Tell me how you want to continue.",
        "es": "Paré. Dime cómo quieres seguir.",
    },
    "nothing_to_cancel": {
        "en": "There is nothing running to cancel.",
        "es": "No hay nada en marcha que cancelar.",
    },
    "unknown_session": {
        "en": "I cannot find that conversation in this project.",
        "es": "No encuentro esa conversación en este proyecto.",
    },
    "empty_message": {"en": "The message is empty.", "es": "El mensaje está vacío."},
    "unknown_message": {"en": "Unknown message: {kind}", "es": "Mensaje desconocido: {kind}"},
    "conversation": {"en": "Conversation", "es": "Conversación"},
}

INSPECT_COMMANDS = {"/estado", "/seleccion", "/status", "/selection"}
TOOL_COMMANDS = {"/herramientas", "/tools"}


def normalize_lang(value: str | None) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    if text.startswith("es"):
        return "es"
    return "en"


def tr(lang: str | None, key: str, **values: object) -> str:
    table = STRINGS[key]
    template = table.get(normalize_lang(lang), table["en"])
    return template.format(**values) if values else template
