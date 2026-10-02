"""Calcula la siguiente versión del plugin a partir de los commits desde el último tag.

Solo cuentan los commits que tocan lo que va dentro del ZIP. Los commits del
bot de release y los cambios de documentación o de la landing no publican.

Conventional Commits:
- `feat!:` o `BREAKING CHANGE` → major (minor mientras la versión sea 0.x)
- `feat:` → minor
- cualquier otro → patch

Uso: python .github/scripts/next_version.py [--bump patch|minor|major]
Escribe `version`, `tag`, `previous` y `bump` en $GITHUB_OUTPUT si existe.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

RELEASE_PATHS = (
    "app/src/",
    "app/icons/",
    "app/plugin.json",
    "app/ipc_entry.py",
    "app/requirements.txt",
    "app/packaging/metadata.json",
)
BOT_SUBJECT = "chore(release):"
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
BREAKING_RE = re.compile(r"^\w+(\([^)]*\))?!:")
FEAT_RE = re.compile(r"^feat(\([^)]*\))?:")
LEVELS = {"patch": 0, "minor": 1, "major": 2}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def last_tag() -> tuple[str | None, tuple[int, int, int]]:
    tags = git("tag", "--list", "v*", "--sort=-v:refname", "--merged", "HEAD").splitlines()
    for tag in tags:
        match = TAG_RE.match(tag)
        if match:
            return tag, tuple(int(part) for part in match.groups())
    return None, (0, 0, 0)


def touches_release(commit: str) -> bool:
    files = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).splitlines()
    return any(path.startswith(RELEASE_PATHS) for path in files)


def detect_bump(since: str | None) -> str | None:
    span = f"{since}..HEAD" if since else "HEAD"
    commits = git("rev-list", "--no-merges", span).splitlines()
    level = None
    for commit in commits:
        subject = git("log", "-1", "--format=%s", commit)
        if subject.startswith(BOT_SUBJECT) or not touches_release(commit):
            continue
        body = git("log", "-1", "--format=%b", commit)
        if BREAKING_RE.match(subject) or "BREAKING CHANGE" in body:
            current = "major"
        elif FEAT_RE.match(subject):
            current = "minor"
        else:
            current = "patch"
        if level is None or LEVELS[current] > LEVELS[level]:
            level = current
    return level


def bump_version(base: tuple[int, int, int], level: str) -> str:
    major, minor, patch = base
    if level == "major" and major == 0:
        level = "minor"
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bump", choices=sorted(LEVELS), help="Fuerza el nivel de la versión")
    args = parser.parse_args()

    previous, base = last_tag()
    level = args.bump or detect_bump(previous)
    result = {"previous": previous or "", "bump": level or "", "version": "", "tag": ""}
    if level:
        version = bump_version(base, level)
        result.update(version=version, tag=f"v{version}")
        print(f"{previous or 'sin tag'} → v{version} ({level})")
    else:
        print(f"Sin cambios del plugin desde {previous or 'el inicio'}: no hay release")

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            for key, value in result.items():
                handle.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
