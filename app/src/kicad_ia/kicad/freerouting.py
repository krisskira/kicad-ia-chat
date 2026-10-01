"""Descarga verificada y ejecución headless de FreeRouting.

Versión fijada: 2.0.1 (Java 17+). Motivo: 2.1.x ignora max_passes en headless
y puede no escribir SES; 2.2+ exige Java 25. SHA-256 del JAR oficial en
FREEROUTING_SHA256; caché en KICAD_IA_CACHE o ~/Library/Caches/kicad-ia.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

# 2.0.1 respeta -mp en headless y escribe SES aunque queden redes sin rutear.
# 2.1.x ignora max_passes y puede no terminar; 2.2+ exige Java 25.
FREEROUTING_VERSION = "2.0.1"
FREEROUTING_URL = f"https://github.com/freerouting/freerouting/releases/download/v{FREEROUTING_VERSION}/freerouting-{FREEROUTING_VERSION}.jar"
FREEROUTING_SHA256 = os.environ.get(
    "FREEROUTING_SHA256",
    "d7fd0f63f52e6d74b0fad6715f87ca9f0ffd7109d66b2a584638000270592ecf",
)
_LOCK = threading.Lock()


def cache_dir() -> Path:
    base = os.environ.get("KICAD_IA_CACHE")
    if base:
        root = Path(base)
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Caches" / "kicad-ia"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kicad-ia"
    path = root / "freerouting"
    path.mkdir(parents=True, exist_ok=True)
    return path


def jar_path() -> Path:
    configured = os.environ.get("FREEROUTING_JAR", "").strip()
    if configured:
        return Path(configured)
    return cache_dir() / f"freerouting-{FREEROUTING_VERSION}.jar"


def _java_candidates(configured: str = "") -> list[str]:
    found: list[str] = []

    def add(path: str | Path | None) -> None:
        if not path:
            return
        text = str(path)
        if text and text not in found:
            found.append(text)

    add(configured)
    add(os.environ.get("JAVA_BIN", "").strip())
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        add(Path(java_home) / "bin" / "java")
        if sys.platform == "win32":
            add(Path(java_home) / "bin" / "java.exe")
    which = shutil.which("java")
    add(which)

    if sys.platform == "darwin":
        home_tool = Path("/usr/libexec/java_home")
        if home_tool.is_file():
            for version in ("21", "17", "23", "11"):
                try:
                    proc = subprocess.run(
                        [str(home_tool), "-v", version],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    root = (proc.stdout or "").strip()
                    if proc.returncode == 0 and root:
                        add(Path(root) / "bin" / "java")
                except (OSError, subprocess.TimeoutExpired):
                    pass
            try:
                proc = subprocess.run([str(home_tool)], capture_output=True, text=True, timeout=5, check=False)
                root = (proc.stdout or "").strip()
                if proc.returncode == 0 and root:
                    add(Path(root) / "bin" / "java")
            except (OSError, subprocess.TimeoutExpired):
                pass
        jvms = Path("/Library/Java/JavaVirtualMachines")
        if jvms.is_dir():
            for home in sorted(jvms.glob("*/Contents/Home/bin/java"), reverse=True):
                add(home)
        for brew in (
            "/opt/homebrew/opt/openjdk@21/bin/java",
            "/opt/homebrew/opt/openjdk@17/bin/java",
            "/opt/homebrew/opt/openjdk/bin/java",
            "/usr/local/opt/openjdk@21/bin/java",
            "/usr/local/opt/openjdk@17/bin/java",
            "/usr/local/opt/openjdk/bin/java",
        ):
            add(brew)
    elif sys.platform.startswith("linux"):
        for root in (Path("/usr/lib/jvm"), Path("/usr/lib64/jvm")):
            if not root.is_dir():
                continue
            for home in sorted(root.glob("*/bin/java"), reverse=True):
                add(home)
    elif sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        for base_name in ("Eclipse Adoptium", "Java", "Microsoft", "Amazon Corretto"):
            base = Path(program_files) / base_name
            if base.is_dir():
                for home in sorted(base.glob("*/bin/java.exe"), reverse=True):
                    add(home)
    return found


def find_java(configured: str = "") -> str | None:
    for candidate in _java_candidates(configured):
        path = Path(candidate)
        if not path.is_file():
            continue
        if sys.platform == "win32" or os.access(path, os.X_OK):
            return str(path)
    return None


def java_version(java_bin: str) -> tuple[int, str] | None:
    proc = subprocess.run([java_bin, "-version"], capture_output=True, text=True, timeout=15, check=False)
    text = (proc.stderr or proc.stdout or "").strip()
    match = re.search(r'version "(\d+)(?:\.\d+)*"', text)
    if not match:
        # Formatos antiguos: 1.8.0_xxx
        match = re.search(r'version "1\.(\d+)', text)
        if match:
            return int(match.group(1)), text.splitlines()[0] if text else match.group(0)
        return None
    return int(match.group(1)), text.splitlines()[0] if text else str(match.group(1))


def probe_java(configured: str = "") -> dict:
    """Resuelve Java y su versión. Útil para la UI de ajustes."""
    path = find_java(configured)
    if not path:
        return {
            "ok": False,
            "error": (
                "No encuentro Java 17+. Instálalo (Temurin/OpenJDK) o indica la ruta en Ajustes. "
                "En macOS, KiCad a veces no ve el Java del PATH: usa la detección automática o pega "
                "…/Contents/Home/bin/java."
            ),
            "candidates_tried": _java_candidates(configured)[:12],
        }
    version = java_version(path)
    if version is None:
        return {"ok": False, "java": path, "error": f"No pude leer la versión de {path}."}
    major, label = version
    ok = major >= 17
    return {
        "ok": ok,
        "java": path,
        "major": major,
        "label": label,
        "error": None if ok else f"FreeRouting necesita Java 17+; tienes {label}.",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_jar(url: str = FREEROUTING_URL, expected_sha: str | None = None, allow_download: bool = True) -> dict:
    """Devuelve la ruta del JAR. Descarga al primer uso si hace falta."""
    expected = (expected_sha or FREEROUTING_SHA256).lower()
    path = jar_path()
    with _LOCK:
        if path.is_file():
            digest = sha256_file(path)
            if expected.startswith("placeholder") or digest == expected:
                if expected.startswith("placeholder"):
                    log.warning("FreeRouting sin SHA fijado; usando el JAR local %s (%s)", path, digest)
                return {"ok": True, "jar": str(path), "sha256": digest, "downloaded": False}
            return {
                "ok": False,
                "error": (
                    f"El JAR de FreeRouting no coincide con el SHA-256 esperado.\n"
                    f"Esperado: {expected}\nObtenido: {digest}\nBorra {path} para reintentar."
                ),
            }
        if not allow_download:
            return {"ok": False, "error": f"No está FreeRouting en {path}. Activa la descarga o define FREEROUTING_JAR."}
        lock = cache_dir() / "download.lock"
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return {"ok": False, "error": "Otra descarga de FreeRouting está en curso. Espera un momento."}
        try:
            partial = path.with_suffix(".jar.partial")
            log.info("Descargando FreeRouting %s…", FREEROUTING_VERSION)
            urllib.request.urlretrieve(url, partial)  # noqa: S310 — URL fija HTTPS de GitHub Releases
            digest = sha256_file(partial)
            if not expected.startswith("placeholder") and digest != expected:
                partial.unlink(missing_ok=True)
                return {"ok": False, "error": f"SHA-256 incorrecto tras descargar FreeRouting: {digest}"}
            partial.replace(path)
            (cache_dir() / f"freerouting-{FREEROUTING_VERSION}.jar.sha256").write_text(digest + "\n", encoding="utf-8")
            return {"ok": True, "jar": str(path), "sha256": digest, "downloaded": True}
        except Exception as exc:
            return {"ok": False, "error": f"No pude descargar FreeRouting: {exc}"}
        finally:
            lock.unlink(missing_ok=True)


def run_freerouting(
    dsn: Path,
    ses: Path,
    java_bin: str | None = None,
    jar: str | None = None,
    timeout_s: int = 300,
    max_passes: int = 100,
    ignore_net_classes: list[str] | None = None,
) -> dict:
    java = java_bin or find_java()
    if not java:
        return {
            "ok": False,
            "error": (
                "No encuentro Java. Instala un JDK 17+ (Temurin/OpenJDK), define JAVA_BIN "
                "o elige la ruta en Ajustes del chat."
            ),
        }
    version = java_version(java)
    if version and version[0] < 17:
        return {"ok": False, "error": f"FreeRouting {FREEROUTING_VERSION} necesita Java 17 o superior; tienes {version[1]}."}
    jar_info = {"ok": True, "jar": jar} if jar else ensure_jar()
    if not jar_info.get("ok"):
        return jar_info
    ses.parent.mkdir(parents=True, exist_ok=True)
    passes = max(1, int(max_passes))
    args = [
        java,
        "-Xmx1024m",
        "-jar",
        jar_info["jar"],
        "--gui.enabled=false",
        "-de",
        str(dsn),
        "-do",
        str(ses),
        "-mp",
        str(passes),
        f"--router.max_passes={passes}",
    ]
    if ignore_net_classes:
        args.extend(["-inc", ",".join(ignore_net_classes)])
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"" if isinstance(exc.stdout, bytes) else exc.stdout) or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        return {
            "ok": False,
            "error": f"FreeRouting superó el timeout de {timeout_s}s sin generar SES.",
            "returncode": None,
            "log_tail": str(stdout)[-1500:],
        }
    if not ses.is_file() or ses.stat().st_size < 8:
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout).strip() or "FreeRouting no generó el SES.",
            "returncode": proc.returncode,
            "log_tail": (proc.stdout or "")[-1500:],
        }
    return {
        "ok": True,
        "ses": str(ses),
        "returncode": proc.returncode,
        "jar": jar_info["jar"],
        "log_tail": (proc.stdout or proc.stderr or "")[-800:],
        "max_passes": passes,
    }


def route_board_files(
    board_file: Path,
    work_dir: Path | None = None,
    timeout_s: int = 300,
    max_passes: int = 100,
    ignore_net_classes: list[str] | None = None,
    java_bin: str | None = None,
    fab: dict | None = None,
    export_dsn=None,
    import_ses=None,
    apply_fab_rules=None,
) -> dict:
    """DSN -> FreeRouting -> SES -> placa candidata. Deja artefactos en work_dir."""
    from kicad_ia.kicad import pcbnew_bridge

    export_dsn = export_dsn or pcbnew_bridge.export_dsn
    import_ses = import_ses or pcbnew_bridge.import_ses
    apply_fab_rules = apply_fab_rules or pcbnew_bridge.apply_fab_rules
    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="kicad-ia-route-"))
    root.mkdir(parents=True, exist_ok=True)
    dsn = root / "board.dsn"
    ses = root / "board.ses"
    candidate = root / "board-routed.kicad_pcb"
    shutil.copy2(board_file, root / "board-source.kicad_pcb")
    source = root / "board-source.kicad_pcb"
    if fab:
        tuned = apply_fab_rules(source, fab)
        if not tuned.get("ok"):
            return {**tuned, "work_dir": str(root)}
    exported = export_dsn(source, dsn)
    if not exported.get("ok"):
        return {**exported, "work_dir": str(root)}
    routed = run_freerouting(
        dsn,
        ses,
        java_bin=java_bin,
        timeout_s=timeout_s,
        max_passes=max_passes,
        ignore_net_classes=ignore_net_classes,
    )
    if not routed.get("ok"):
        return {**routed, "work_dir": str(root), "dsn": str(dsn)}
    imported = import_ses(source, ses, candidate)
    if not imported.get("ok"):
        return {**imported, "work_dir": str(root), "dsn": str(dsn), "ses": str(ses)}
    return {
        "ok": True,
        "work_dir": str(root),
        "dsn": str(dsn),
        "ses": str(ses),
        "candidate": str(candidate),
        "freerouting": routed,
        "fab": fab or {},
    }
