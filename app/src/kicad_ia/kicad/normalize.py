"""Normaliza ítems de KiCad a diccionarios que el modelo puede leer."""

from __future__ import annotations


def text_value(obj: object) -> str:
    if obj is None or isinstance(obj, (int, float, bool)):
        return ""
    if isinstance(obj, str):
        return obj
    value = getattr(obj, "value", None)
    if isinstance(value, str):
        return value
    text = getattr(obj, "text", None)
    if text is not None and text is not obj:
        inner = getattr(text, "value", None)
        if isinstance(inner, str):
            return inner
        if isinstance(text, str):
            return text
    return ""


def lib_id_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    nickname = getattr(value, "library_nickname", None) or getattr(value, "lib_nickname", None)
    entry = getattr(value, "entry_name", None) or getattr(value, "item_name", None)
    if nickname and entry:
        return f"{nickname}:{entry}"
    return str(value)


def _model_names(item: object) -> list[str]:
    definition = getattr(item, "definition", None)
    source = definition if definition is not None else item
    names: list[str] = []
    try:
        models = getattr(source, "models", []) or []
    except Exception:
        return names
    for model in models:
        filename = getattr(model, "filename", "") or ""
        if filename:
            names.append(str(filename))
    return names


def _pad_nets(item: object) -> list[str]:
    definition = getattr(item, "definition", None)
    source = definition if definition is not None else item
    nets: list[str] = []
    try:
        pads = list(getattr(source, "pads", []) or [])
    except Exception:
        return nets
    for pad in pads[:40]:
        net = getattr(pad, "net", None)
        name = getattr(net, "name", None) if net is not None else None
        if name and name not in nets:
            nets.append(str(name))
    return nets


def normalize_item(item: object, editor: str) -> dict:
    lib = getattr(item, "lib_id", None)
    if not lib:
        definition = getattr(item, "definition", None)
        lib = getattr(definition, "id", None) if definition is not None else None
    item_id = getattr(item, "id", None)
    reference = text_value(getattr(item, "reference_field", None)) or str(
        getattr(item, "reference", "") or ""
    )
    value = text_value(getattr(item, "value_field", None))
    if not value:
        raw_value = getattr(item, "value", None)
        value = raw_value if isinstance(raw_value, str) else text_value(raw_value)
    return {
        "editor": editor,
        "kind": type(item).__name__,
        "id": "" if item_id is None else str(item_id),
        "reference": reference,
        "value": value,
        "lib_id": lib_id_text(lib),
        "footprint": text_value(getattr(item, "footprint_field", None)),
        "nets": _pad_nets(item),
        "models": _model_names(item),
    }
