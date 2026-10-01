"""Enlaza esta carpeta como plugin IPC de KiCad."""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def plugin_dirs() -> list[Path]:
    root = Path.home() / "Documents" / "KiCad"
    if not root.is_dir():
        return []
    found = []
    for version in sorted(path for path in root.iterdir() if path.is_dir()):
        plugins = version / "plugins"
        plugins.mkdir(exist_ok=True)
        found.append(plugins)
    return found


def link() -> list[Path]:
    created = []
    for directory in plugin_dirs():
        target = directory / "kicad-ia"
        if target.is_symlink() or target.exists():
            print(f"ya existe {target}")
            continue
        target.symlink_to(APP, target_is_directory=True)
        created.append(target)
        print(f"enlazado {target} -> {APP}")
    if not created and not plugin_dirs():
        print("No hay ~/Documents/KiCad/<versión>. Abre KiCad una vez y vuelve a ejecutar.")
    return created


if __name__ == "__main__":
    link()
    sys.exit(0)
