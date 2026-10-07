"""Carpeta de copias y trabajo temporal del plugin, fuera de la raíz del proyecto.

Las del plugin van en «<proyecto>-backups/kicad-ia/». Ahí caben esquemáticos,
placas y el trabajo de autoruteo (antes «kicad-ia-route-*» en la raíz).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

PLUGIN_BACKUP_LEAF = "kicad-ia"


def plugin_backup_dir(project_dir: Path, project_name: str = "") -> Path:
    """<carpeta-del-proyecto>/<nombre>-backups/kicad-ia/."""
    root = Path(project_dir)
    stem = str(project_name or root.name).strip() or root.name
    if stem.endswith(".kicad_pro"):
        stem = stem[: -len(".kicad_pro")]
    path = root / f"{stem}-backups" / PLUGIN_BACKUP_LEAF
    path.mkdir(parents=True, exist_ok=True)
    ignore = path / ".gitignore"
    if not ignore.is_file():
        try:
            ignore.write_text("*\n", encoding="utf-8")
        except OSError:
            pass
    return path


def plugin_temp_dir(project_dir: Path | None, prefix: str, project_name: str = "") -> Path:
    """Directorio temporal bajo la carpeta del plugin (p. ej. autoruteo)."""
    if project_dir is None:
        return Path(tempfile.mkdtemp(prefix=prefix))
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(plugin_backup_dir(project_dir, project_name))))
