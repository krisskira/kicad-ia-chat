#!/usr/bin/env sh
# Instala KiCad IA en ~/Documents/KiCad/<versión>/plugins/kicad-ia
set -eu

REPO="${KICAD_IA_REPO:-krisskira/kicad-ia-pluging}"
API="https://api.github.com/repos/${REPO}"
VERSION=""
KICAD_VERSION=""
UNINSTALL=0

usage() {
  cat <<'EOF'
Uso: install.sh [--version X.Y.Z] [--kicad-version V] [--uninstall] [--help]

  --version X.Y.Z       Versión del plugin (por defecto: último release)
  --kicad-version V     Carpeta de KiCad (por ejemplo 10.0). Por defecto: la más nueva
  --uninstall           Quita plugins/kicad-ia
  --help                Esta ayuda

Ejemplos:
  curl -fsSL https://raw.githubusercontent.com/krisskira/kicad-ia-pluging/main/install/install.sh | sh
  sh install.sh --version 0.1.0 --kicad-version 10.0
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --kicad-version)
      KICAD_VERSION="${2:-}"
      shift 2
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Opción desconocida: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Falta el comando: $1" >&2
    exit 1
  fi
}

need_cmd curl
need_cmd unzip
need_cmd mktemp

documents_dir() {
  if [ "$(uname -s)" = "Darwin" ]; then
    echo "${HOME}/Documents"
  else
    if command -v xdg-user-dir >/dev/null 2>&1; then
      xdg-user-dir DOCUMENTS
    else
      echo "${HOME}/Documents"
    fi
  fi
}

kicad_root() {
  echo "$(documents_dir)/KiCad"
}

list_kicad_versions() {
  root="$(kicad_root)"
  if [ ! -d "$root" ]; then
    return 0
  fi
  # Orden natural: 9.0, 10.0, …
  find "$root" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort -V
}

pick_kicad_version() {
  if [ -n "$KICAD_VERSION" ]; then
    echo "$KICAD_VERSION"
    return 0
  fi
  versions="$(list_kicad_versions)"
  if [ -z "$versions" ]; then
    echo "No hay $(kicad_root)/<versión>. Abre KiCad una vez y vuelve a ejecutar." >&2
    exit 1
  fi
  echo "$versions" | tail -n 1
}

plugins_dir_for() {
  echo "$(kicad_root)/$1/plugins"
}

uninstall_plugin() {
  version="$(pick_kicad_version)"
  target="$(plugins_dir_for "$version")/kicad-ia"
  if [ -e "$target" ] || [ -L "$target" ]; then
    rm -rf "$target"
    echo "Eliminado $target"
  else
    echo "No está instalado en $target"
  fi
  bak="$(plugins_dir_for "$version")/kicad-ia.bak"
  if [ -e "$bak" ] || [ -L "$bak" ]; then
    rm -rf "$bak"
    echo "Eliminado $bak"
  fi
}

latest_tag() {
  curl -fsSL "${API}/releases/latest" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

resolve_tag() {
  if [ -n "$VERSION" ]; then
    case "$VERSION" in
      v*) echo "$VERSION" ;;
      *) echo "v${VERSION}" ;;
    esac
    return 0
  fi
  tag="$(latest_tag)"
  if [ -z "$tag" ]; then
    echo "No hay releases en ${REPO}" >&2
    exit 1
  fi
  echo "$tag"
}

version_from_tag() {
  echo "$1" | sed 's/^v//'
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "Falta sha256sum o shasum" >&2
    exit 1
  fi
}

verify_checksum() {
  file="$1"
  sums="$2"
  name="$(basename "$file")"
  expected="$(awk -v n="$name" '$2 == n { print $1; exit }' "$sums")"
  if [ -z "$expected" ]; then
    echo "SHA256SUMS no incluye $name" >&2
    exit 1
  fi
  actual="$(sha256_of "$file")"
  if [ "$actual" != "$expected" ]; then
    echo "Checksum incorrecto para $name" >&2
    echo "  esperado: $expected" >&2
    echo "  obtenido: $actual" >&2
    exit 1
  fi
  echo "Checksum OK ($name)"
}

install_plugin() {
  tag="$(resolve_tag)"
  ver="$(version_from_tag "$tag")"
  kver="$(pick_kicad_version)"
  plugins="$(plugins_dir_for "$kver")"
  zip_name="kicad-ia-${ver}.zip"
  asset_base="https://github.com/${REPO}/releases/download/${tag}"

  echo "Release: ${tag}"
  echo "KiCad:   ${kver} → ${plugins}"

  mkdir -p "$plugins"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT INT TERM

  echo "Descargando ${zip_name}…"
  curl -fsSL "${asset_base}/${zip_name}" -o "${tmp}/${zip_name}"
  curl -fsSL "${asset_base}/SHA256SUMS" -o "${tmp}/SHA256SUMS"
  verify_checksum "${tmp}/${zip_name}" "${tmp}/SHA256SUMS"

  extract="${tmp}/extract"
  mkdir -p "$extract"
  unzip -q "${tmp}/${zip_name}" -d "$extract"

  if [ ! -f "${extract}/plugin.json" ]; then
    echo "El ZIP no tiene plugin.json en la raíz" >&2
    exit 1
  fi

  target="${plugins}/kicad-ia"
  bak="${plugins}/kicad-ia.bak"
  if [ -e "$target" ] || [ -L "$target" ]; then
    rm -rf "$bak"
    mv "$target" "$bak"
    echo "Copia anterior en $bak"
  fi
  mkdir -p "$target"
  # Copia el contenido del ZIP a kicad-ia/
  cp -R "${extract}/." "$target/"

  echo "Instalado en $target"
  echo "Reinicia KiCad, abre el editor de PCB y pulsa KiCad IA."
  echo "La primera vez hace falta red: KiCad instala requirements.txt."
}

if [ "$UNINSTALL" -eq 1 ]; then
  uninstall_plugin
else
  install_plugin
fi
