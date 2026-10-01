# Página pública

README y GitHub Pages explican el uso: instalación, ajustes y el flujo del chat a la placa.

Un chat arma el esquemático de KiCad con las bibliotecas configuradas. Si la pieza no está, no se inventa. A la placa se pasa con F8. Colocar y autorutear se aplican cuando el usuario confirma.

No van en la página el roadmap, LCSC ni la tabla de herramientas. Eso sigue en [`app/README.md`](../app/README.md) y [`app/doc/roadmap.md`](../app/doc/roadmap.md).

| Qué | Dónde |
|-----|--------|
| Textos | `landing-page/content/` |
| Portada | `landing-page/public/media/og-cover.svg` |
| Diagrama y capturas | `landing-page/public/media/flujo.svg`, `chat-inicio.png`, `chat-ajustes.png` |
| Repetir capturas | `landing-page/resources/capturar-chat.py` (chat en marcha y KiCad abierto) |
| Publicación | `.github/workflows/pages.yml` |
| Template | `git@github.com:krisskira/kriver-template-projects.git` |

URL: <https://krisskira.github.io/kicad-ia-pluging/>. En el repositorio, Pages → Source: GitHub Actions.
