# Página pública

README y GitHub Pages explican el uso: instalación, ajustes y el flujo del chat a la placa.

Un chat arma el esquemático de KiCad con las bibliotecas configuradas. Si la pieza no está, no se inventa. A la placa se pasa con F8. Colocar y autorutear se aplican cuando el usuario confirma.

No van en la página el roadmap, LCSC ni la tabla de herramientas. Eso sigue en [`app/README.md`](../app/README.md) y [`app/doc/roadmap.md`](../app/doc/roadmap.md).

| Qué | Dónde |
|-----|--------|
| Textos | `landing-page/content/` |
| Portada | `landing-page/public/media/es/og-cover.svg` y `og-cover.png`. Inglés: los mismos nombres en `media/en/`. La página estática usa la portada en español |
| Diagrama y capturas | `flujo.svg`, `chat-inicio.png`, `chat-acciones.png` y `chat-ajustes.png` en `media/es/` y `media/en/`. La landing elige la carpeta según el idioma |
| Fotogramas y video | `public/media/recorridos/<recorrido>/<idioma>/`: fotogramas, `<recorrido>.mp4`, `.webm` y `.vtt`. Hay un video narrado por idioma y la página carga el del idioma seleccionado |
| Repetir capturas | Chat de prueba con `KICAD_MODE=fake` y `landing-page/resources/capturar-chat.py --lang es` y `--lang en`. Fotogramas: `recorridos/proyecto_demo.py` y después `recorridos/capturas.py --lang es` y `--lang en` |
| Recorridos | Secciones `walkthrough` en `landing.json`: «De la orden a la PCB» y «Configuración inicial». Fotogramas, videos y subtítulos en `landing-page/public/media/recorridos/` |
| Repetir recorridos | `landing-page/resources/recorridos/` (ver abajo) |
| SEO y analítica | `site.json`: metas, JSON-LD (`SoftwareApplication` con su `SoftwareSourceCode` en `isBasedOn`, `Person` y `Organization` Kriver Device) y `gtm` (Google Tag Manager). Sin `keywords`: Google no los usa |
| Publicación | `.github/workflows/pages.yml` |
| Template | `git@github.com:krisskira/kriver-template-projects.git` |

URL: <https://krisskira.github.io/kicad-ia-chat/>. En el repositorio, Pages → Source: GitHub Actions.

## Recorridos

El chat es la interfaz real en modo `fake` con eventos inyectados. Esquemático, placas y 3D salen de KiCad 10 y FreeRouting con un proyecto de ejemplo (LED por USB-C). El primer fotograma de «De la orden a la PCB» es la ventana real de KiCad, con el icono de KiCad IA resaltado (`resaltar_boton.py`, a partir de `fuentes/boton-kicad.png`). Las otras ventanas de KiCad del recorrido son ilustración y los tokens son de ejemplo; la página lo dice. No hay clave real: la de Ajustes es de ejemplo.

Necesita macOS (voces `say` Paulina y Samantha), KiCad 10 en `/Applications`, Java 17+, Chrome y `ffmpeg` con libx264, libvpx-vp9 y libopus. Desde la raíz del repo:

```bash
PYTHONPATH=app/src app/.venv/bin/python landing-page/resources/recorridos/proyecto_demo.py
cd landing-page/resources/recorridos
PYTHONPATH=../../../app/src ../../../app/.venv/bin/python capturas.py
cd ../.. && python3 resources/recorridos/video.py
```

`proyecto_demo.py` busca el Python de KiCad para `placa_kicad.py` y deja todo en `/tmp/kicad-ia-recorrido`. FreeRouting no es determinista: las cifras (pistas, cobre, DRC) se leen de `resumen.json` en cada corrida. La narración y los subtítulos están en `guion.json`; si cambias un texto, repite `video.py`. Las escenas deben coincidir en número con los fotogramas.
