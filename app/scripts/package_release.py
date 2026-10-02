"""Empaqueta el plugin para GitHub Release y el Gestor de complementos (PCM)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
PACKAGING = APP / "packaging"
DIST = REPO / "dist"
PLUGIN_FILES = ("plugin.json", "requirements.txt", "ipc_entry.py")
ICON_NAMES = (
    "kicad-ia-light-24.png",
    "kicad-ia-light-48.png",
    "kicad-ia-dark-24.png",
    "kicad-ia-dark-48.png",
)
EXCLUDE_DIR_NAMES = {".venv", "__pycache__", ".pytest_cache", ".easyeda_cache", ".git"}
EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo"}
EXCLUDE_FILE_NAMES = {".DS_Store", ".env"}


def read_version() -> str:
    text = (APP / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("No hay version en pyproject.toml")
    return match.group(1)


def ensure_icons() -> None:
    missing = [name for name in ICON_NAMES if not (APP / "icons" / name).is_file()]
    if not missing:
        return
    print("Generando iconos…")
    subprocess.run([sys.executable, str(APP / "scripts" / "make_icons.py")], check=True)
    still = [name for name in ICON_NAMES if not (APP / "icons" / name).is_file()]
    if still:
        raise SystemExit(f"Faltan iconos: {', '.join(still)}")


def should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_FILE_NAMES or path.name in EXCLUDE_DIR_NAMES:
        return True
    if path.suffix in EXCLUDE_FILE_SUFFIXES:
        return True
    return any(part in EXCLUDE_DIR_NAMES for part in path.parts)


def copy_plugin_tree(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in PLUGIN_FILES:
        shutil.copy2(APP / name, dest / name)
    icons = dest / "icons"
    icons.mkdir(exist_ok=True)
    for name in ICON_NAMES:
        shutil.copy2(APP / "icons" / name, icons / name)
    src_root = APP / "src"
    for path in src_root.rglob("*"):
        if should_skip(path):
            continue
        rel = path.relative_to(src_root)
        target = dest / "src" / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def zip_directory(source: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_dir():
                continue
            archive.write(path, path.relative_to(source).as_posix())


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_metadata() -> dict:
    path = PACKAGING / "metadata.json"
    if not path.is_file():
        raise SystemExit(f"Falta {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def pcm_metadata_for_zip(version: str) -> dict:
    metadata = load_metadata()
    for entry in metadata.get("versions", []):
        for key in ("download_url", "download_sha256", "download_size", "install_size"):
            entry.pop(key, None)
    version_entry = {
        "version": version,
        "status": "testing",
        "kicad_version": "10.0",
        "runtime": "ipc",
        "platforms": ["windows", "macos", "linux"],
    }
    others = [item for item in metadata.get("versions", []) if item.get("version") != version]
    metadata["versions"] = [version_entry, *others]
    return metadata


def install_size_from_zip(zip_path: Path) -> int:
    total = 0
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                total += info.file_size
    return total


def update_pcm_index(version: str, pcm_zip: Path, release_tag: str, repo: str) -> None:
    download_url = (
        f"https://github.com/{repo}/releases/download/{release_tag}/{pcm_zip.name}"
    )
    metadata = load_metadata()
    version_entry = {
        "version": version,
        "status": "testing",
        "kicad_version": "10.0",
        "runtime": "ipc",
        "platforms": ["windows", "macos", "linux"],
        "download_url": download_url,
        "download_sha256": sha256_file(pcm_zip),
        "download_size": pcm_zip.stat().st_size,
        "install_size": install_size_from_zip(pcm_zip),
    }
    versions = [item for item in metadata.get("versions", []) if item.get("version") != version]
    metadata["versions"] = [version_entry, *versions]

    packages_path = PACKAGING / "packages.json"
    write_json(packages_path, {"packages": [metadata]})

    now = int(time.time())
    repository = {
        "$schema": "https://go.kicad.org/pcm/schemas/v1",
        "name": "KiCad IA",
        "maintainer": {
            "name": "Krisskira",
            "contact": {
                "github": "https://github.com/krisskira",
            },
        },
        "packages": {
            "url": f"https://raw.githubusercontent.com/{repo}/main/app/packaging/packages.json",
            "sha256": sha256_file(packages_path),
            "update_timestamp": now,
            "update_time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now)),
        },
    }
    write_json(PACKAGING / "repository.json", repository)
    print(f"Actualizado {packages_path}")
    print(f"Actualizado {PACKAGING / 'repository.json'}")


def try_validate(path: Path) -> None:
    try:
        from kipy.packaging.validate import validate
    except ImportError:
        print("kicad-python no disponible: se omite la validación")
        return
    report = validate(str(path))
    errors = [message for message in report.messages if message.level == "error"]
    for message in report.messages:
        print(f"[{message.level}] {message.path or path.name}: {message.message}")
    if errors:
        raise SystemExit(f"Validación fallida: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-index",
        action="store_true",
        help="Actualiza app/packaging/packages.json y repository.json con el ZIP PCM",
    )
    parser.add_argument(
        "--release-tag",
        default="",
        help="Tag del release (por defecto v<version>)",
    )
    parser.add_argument(
        "--repo",
        default="krisskira/kicad-ia-chat",
        help="owner/repo de GitHub",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valida el plugin y el ZIP PCM con kicad-python",
    )
    args = parser.parse_args(argv)

    version = read_version()
    ensure_icons()
    DIST.mkdir(parents=True, exist_ok=True)

    plugin_zip = DIST / f"kicad-ia-{version}.zip"
    pcm_zip = DIST / f"kicad-ia-{version}-pcm.zip"
    checksums = DIST / "SHA256SUMS"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        plugin_root = tmp_path / "plugin"
        pcm_root = tmp_path / "pcm"
        copy_plugin_tree(plugin_root)
        copy_plugin_tree(pcm_root / "plugins")
        write_json(pcm_root / "metadata.json", pcm_metadata_for_zip(version))

        if plugin_zip.exists():
            plugin_zip.unlink()
        if pcm_zip.exists():
            pcm_zip.unlink()
        zip_directory(plugin_root, plugin_zip)
        zip_directory(pcm_root, pcm_zip)

        if args.validate:
            try_validate(plugin_root)
            try_validate(pcm_root)

    lines = []
    for path in (plugin_zip, pcm_zip):
        digest = sha256_file(path)
        lines.append(f"{digest}  {path.name}")
        print(f"{path.name}: {digest} ({path.stat().st_size} bytes)")
    checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Escrito {checksums}")

    if args.validate:
        try_validate(pcm_zip)

    if args.update_index:
        tag = args.release_tag or f"v{version}"
        update_pcm_index(version, pcm_zip, tag, args.repo)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
