"""Lector y escritor mínimo del formato S-expression de KiCad.

Una lista es `list`; un átomo sin comillas es `Sym`; un texto entre comillas es `str`.
"""

from __future__ import annotations


class Sym(str):
    """Átomo sin comillas, como `symbol`, `yes` o `1.27`."""


def parse(text: str) -> list:
    stack: list[list] = [[]]
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "(":
            stack.append([])
            i += 1
        elif c == ")":
            if len(stack) == 1:
                raise ValueError("Paréntesis de cierre sin abrir.")
            done = stack.pop()
            stack[-1].append(done)
            i += 1
        elif c == '"':
            j = i + 1
            out = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    nxt = text[j + 1]
                    out.append({"n": "\n", "t": "\t"}.get(nxt, nxt))
                    j += 2
                    continue
                out.append(text[j])
                j += 1
            stack[-1].append("".join(out))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            stack[-1].append(Sym(text[i:j]))
            i = j
    if len(stack) != 1:
        raise ValueError("Faltan paréntesis de cierre.")
    return stack[0]


def head(node) -> str:
    if isinstance(node, list) and node and isinstance(node[0], Sym):
        return str(node[0])
    return ""


def children(node: list, name: str) -> list[list]:
    return [child for child in node[1:] if head(child) == name]


def child(node: list, name: str) -> list | None:
    for item in node[1:]:
        if head(item) == name:
            return item
    return None


def number(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _atom(value) -> str:
    if isinstance(value, Sym):
        return str(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text
    return _quote(str(value))


def dumps(node, indent: int = 0) -> str:
    if not isinstance(node, list):
        return _atom(node)
    simple = all(not isinstance(item, list) for item in node)
    if simple:
        return "(" + " ".join(_atom(item) for item in node) + ")"
    pad = "\t" * (indent + 1)
    parts = []
    inline = []
    for item in node:
        if isinstance(item, list):
            break
        inline.append(_atom(item))
    lines = ["(" + " ".join(inline)]
    for item in node[len(inline):]:
        lines.append(pad + dumps(item, indent + 1))
    parts.append("\n".join(lines))
    return parts[0] + "\n" + "\t" * indent + ")"
