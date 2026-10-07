---
name: kicad-ia-pagina
description: >-
  Página pública de KiCad IA: README, landing y GitHub Pages. Usar al editar
  el README raíz, landing-page/content, la portada o el workflow de Pages.
  El plugin en sí sigue en app/AGENTS.md.
---

# Página de KiCad IA

La página pública explica el uso: instalación, ajustes y el flujo del chat a la placa.

## Referencia

No copies el esquema ni el código del template. Léelos allí:

- Repositorio: `git@github.com:krisskira/kriver-template-projects.git`
- Si está al lado: `../kriver-template-projects`
- Procedimiento: `.cursor/skills/kriver-project-page/SKILL.md` de ese repo
- Esquema JSON: `README.md` de ese repo
- Traer código nuevo, desde `landing-page/`: `node ../../kriver-template-projects/scripts/new-landing.mjs . --update`

## Qué puede decir esta página

Un chat arma el esquemático de KiCad con las piezas de las bibliotecas que ya tienes configuradas. Si la pieza no está, no se inventa. El paso a paso, los cuatro modos de instalación, los Ajustes y el flujo hasta F8 sí van en el README y en la landing.

Eso está en `app/README.md` y en la interfaz del chat. No pongas el roadmap, LCSC ni la tabla de herramientas.

El servidor MCP tiene su sección en el README y en la landing (`#mcp`): qué es, que el modelo lo pone el cliente, que el plugin instalado no lo trae (hace falta clonar), el entorno por sistema y el `mcp.json` de Cursor. El detalle técnico sigue en `app/doc/mcp.md`.

La sección `code` de instalación va en una columna: texto arriba, terminal abajo. Los scripts son un solo bloque con `tabs` (macOS / Linux y Windows), cada pestaña con su texto y su código. Ese diseño vive en `src/sections/Code.jsx` del template.

Google Analytics entra por Google Tag Manager: `gtm` en `content/site.json`. El plugin del template pone el script en `<head>` y el `<noscript>` tras `<body>`.

## Archivos de este proyecto

- `README.md`
- `docs/pagina.md`
- `landing-page/content/` y `landing-page/public/media/`
- `.github/workflows/pages.yml` → `https://krisskira.github.io/kicad-ia-chat`

No editar `landing-page/src/`. El arranque y el mapa del código siguen en `app/README.md`.
