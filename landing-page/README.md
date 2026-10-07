# Landing de KiCad IA

Generada con el template de landings (`kriver-template-projects`).
Se publica en <https://krisskira.github.io/kicad-ia-chat/>.

```bash
npm install
npm run dev
npm run build
```

- Textos: `content/landing.json` y `content/site.json`
- Inglés: `content/en.json` (la clave es el texto en español, exacto)
- Colores: `content/theme.css`
- Portada: `public/media/es/og-cover.svg` (inglés en `public/media/en/`)

El código (`src/`, el plugin, `index.html`) viene del template. Para traerlo de nuevo, desde esta carpeta:

```bash
node ../../kriver-template-projects/scripts/new-landing.mjs . --update
```

Repositorio del template: `git@github.com:krisskira/kriver-template-projects.git`.

El workflow `.github/workflows/pages.yml` publica cada push a `main` que toque `landing-page/`. En el repositorio: **Settings → Pages → Source: GitHub Actions**.
