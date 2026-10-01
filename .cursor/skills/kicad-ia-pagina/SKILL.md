---
name: kicad-ia-pagina
description: >-
  Página pública de KiCad IA: README, landing en Próximamente y GitHub Pages.
  Usar al editar el README raíz, landing-page/content, la portada o el
  workflow de Pages. El plugin en sí sigue en app/AGENTS.md.
---

# Página de KiCad IA

Coming soon. Solo la idea central del plugin.

## Referencia

No copies el esquema ni el código del template. Léelos allí:

- Repositorio: `git@github.com:krisskira/kriver-template-projects.git`
- Si está al lado: `../kriver-template-projects`
- Procedimiento: `.cursor/skills/kriver-project-page/SKILL.md` de ese repo
- Esquema JSON: `README.md` de ese repo
- Traer código nuevo, desde `landing-page/`: `node ../../kriver-template-projects/scripts/new-landing.mjs . --update`

## Qué puede decir esta página

Un chat arma el esquemático de KiCad con las piezas de las bibliotecas que ya tienes configuradas, no con una lista del plugin.

Eso está en `app/README.md`. No pongas en la página el roadmap, LCSC, el revisor, MCP, IPC, FreeRouting ni la tabla de herramientas. Si la pieza no está, no se inventa: eso sí es parte de la idea (`app/AGENTS.md`).

## Archivos de este proyecto

- `README.md`
- `docs/pagina.md`
- `landing-page/content/` y `landing-page/public/media/`
- `.github/workflows/pages.yml` → `https://krisskira.github.io/kicad-ia-pluging`

No editar `landing-page/src/`. El arranque y el mapa del código siguen en `app/README.md`.
