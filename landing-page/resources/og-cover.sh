#!/bin/sh
# Genera public/media/<idioma>/og-cover.png (1200×630) desde og-cover.svg, en español e inglés.
# Las redes sociales no muestran SVG en og:image. Necesita Google Chrome.
# Uso, desde landing-page/: sh resources/og-cover.sh
set -e
cd "$(dirname "$0")/.."
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
for LANG_DIR in es en; do
  SVG="$(pwd)/public/media/$LANG_DIR/og-cover.svg"
  PAGE="$(mktemp -d)/og.html"
  printf '<html><body style="margin:0"><img src="file://%s?v=%s" width="1200" height="630"></body></html>' "$SVG" "$(date +%s)" > "$PAGE"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
    --window-size=1200,630 --screenshot="$(pwd)/public/media/$LANG_DIR/og-cover.png" "file://$PAGE" >/dev/null 2>&1
  rm -rf "$(dirname "$PAGE")"
  echo "public/media/$LANG_DIR/og-cover.png"
done
