import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ROBOTS = 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1';

function readJson(root, file) {
  return JSON.parse(readFileSync(resolve(root, 'content', file), 'utf8'));
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function plain(value) {
  return String(value ?? '').replace(/\*\*(.+?)\*\*/g, '$1').replace(/`(.+?)`/g, '$1');
}

function absolute(base, path) {
  if (!path) return undefined;
  if (/^https?:\/\//.test(path)) return path;
  return base ? `${base}/${path.replace(/^\.?\//, '')}` : undefined;
}

const IMAGE_TYPES = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif' };

function imageType(path) {
  return IMAGE_TYPES[String(path).split('?')[0].split('.').pop().toLowerCase()];
}

function heroOf(landing) {
  return landing.sections.find((section) => section.type === 'hero') ?? {};
}

const PAGE_TYPES = new Set(['WebPage', 'ProfilePage', 'AboutPage', 'CollectionPage']);

// En content/ un "@id" puede ser relativo ("#author"); en el JSON-LD va absoluto.
function resolveIds(value, base) {
  if (Array.isArray(value)) return value.map((item) => resolveIds(item, base));
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        key === '@id' && typeof item === 'string' && item.startsWith('#') ? `${base}/${item}` : resolveIds(item, base),
      ]),
    );
  }
  return value;
}

function projectNodes(landing, base, author) {
  return landing.sections
    .filter((section) => section.type === 'projects')
    .flatMap((section) => section.items ?? [])
    .filter((item) => item.schema)
    .map((item) => {
      const link = (item.actions ?? []).find((action) => /^https?:\/\//.test(action.href));
      return {
        '@type': 'CreativeWork',
        name: plain(item.title),
        description: plain(item.summary),
        ...(link ? { url: link.href } : {}),
        ...(item.year ? { dateCreated: String(item.year) } : {}),
        ...(item.tags?.length ? { keywords: item.tags.join(', ') } : {}),
        ...(author ? { author: { '@id': author['@id'] }, creator: { '@id': author['@id'] } } : {}),
        ...resolveIds(item.schema, base),
        '@id': `${base}/#${item.id || slugify(plain(item.title))}`,
      };
    });
}

function slugify(value) {
  return String(value)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function structuredData(site, landing, base) {
  const url = base ? `${base}/` : undefined;
  const author = site.author && { '@type': 'Person', ...resolveIds(site.author, base), '@id': `${base}/#author` };
  const maker = site.maker && { '@type': 'Organization', ...resolveIds(site.maker, base), '@id': `${base}/#maker` };
  const graph = [
    {
      '@type': 'WebSite',
      '@id': `${base}/#website`,
      url,
      name: site.name,
      description: site.description,
      inLanguage: site.lang,
      ...(maker ? { publisher: { '@id': maker['@id'] } } : {}),
    },
  ];

  if (site.schema) {
    const { '@id': schemaId = '#product', ...schema } = resolveIds(site.schema, base);
    const page = PAGE_TYPES.has(schema['@type']);
    const productId = schemaId.startsWith('#') ? `${base}/${schemaId}` : schemaId;
    if (!page) {
      graph.push({
        '@type': 'WebPage',
        '@id': `${base}/#webpage`,
        url,
        name: site.title || site.name,
        description: site.description,
        inLanguage: site.lang,
        isPartOf: { '@id': `${base}/#website` },
        about: { '@id': productId },
        mainEntity: { '@id': productId },
        dateModified: new Date().toISOString().slice(0, 10),
        ...(absolute(base, site.ogImage)
          ? { primaryImageOfPage: { '@type': 'ImageObject', url: absolute(base, site.ogImage) } }
          : {}),
        ...(author ? { author: { '@id': author['@id'] }, creator: { '@id': author['@id'] } } : {}),
        ...(maker ? { publisher: { '@id': maker['@id'] } } : {}),
      });
    }
    graph.push({
      name: site.title || site.name,
      description: site.description,
      url,
      image: absolute(base, site.ogImage),
      ...(page ? { isPartOf: { '@id': `${base}/#website` }, inLanguage: site.lang } : {}),
      ...(author ? { author: { '@id': author['@id'] }, creator: { '@id': author['@id'] } } : {}),
      ...(maker && !page ? { publisher: { '@id': maker['@id'] } } : {}),
      ...(page ? {} : { mainEntityOfPage: { '@id': `${base}/#webpage` } }),
      ...schema,
      '@id': productId,
    });
  }
  if (author) graph.push(author);
  if (maker) graph.push(maker);
  graph.push(...projectNodes(landing, base, author));

  const faq = landing.sections.find((section) => section.type === 'faq');
  if (faq?.items?.length) {
    graph.push({
      '@type': 'FAQPage',
      '@id': `${base}/#faq`,
      mainEntity: faq.items.map((item) => ({
        '@type': 'Question',
        name: plain(item.q),
        acceptedAnswer: { '@type': 'Answer', text: plain(item.a) },
      })),
    });
  }

  return JSON.stringify({ '@context': 'https://schema.org', '@graph': graph }, null, 2);
}

function localeScript(site) {
  const key = JSON.stringify(`${site.slug || 'landing'}-locale`);
  const spanish = JSON.stringify(site.lang || 'es');
  return `(function () {
  try {
    var params = new URLSearchParams(location.search);
    var fromUrl = params.get('lang');
    var stored = localStorage.getItem(${key});
    var locale = fromUrl === 'en' || fromUrl === 'es' ? fromUrl : stored === 'en' || stored === 'es' ? stored : (navigator.language || '').toLowerCase().indexOf('en') === 0 ? 'en' : 'es';
    document.documentElement.lang = locale === 'en' ? 'en' : ${spanish};
  } catch (e) {}
})();`;
}

function themeScript(site) {
  const key = JSON.stringify(`${site.slug || 'landing'}-theme`);
  const fallback = JSON.stringify(site.defaultTheme || 'system');
  return `(function () {
  try {
    var stored = localStorage.getItem(${key});
    var fallback = ${fallback};
    var theme = stored === 'dark' || stored === 'light' ? stored : fallback;
    if (theme === 'system') theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    if (theme === 'dark') document.documentElement.classList.add('dark');
    document.documentElement.style.colorScheme = theme;
  } catch (e) {}
})();`;
}

// Solo un id de contenedor válido llega al HTML: el valor va dentro de un <script>.
function gtmId(site) {
  const id = String(site.gtm ?? '').trim();
  return /^GTM-[A-Z0-9]+$/.test(id) ? id : '';
}

function gtmHead(site) {
  const id = gtmId(site);
  if (!id) return '';
  return `<!-- Google Tag Manager -->
    <script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','${id}');</script>
    <!-- End Google Tag Manager -->`;
}

function gtmBody(site) {
  const id = gtmId(site);
  if (!id) return '';
  return `<!-- Google Tag Manager (noscript) -->
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=${id}"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
    <!-- End Google Tag Manager (noscript) -->`;
}

// Solo un id de proyecto válido llega al HTML: el valor va dentro de un <script>.
function clarityId(site) {
  const id = String(site.clarity ?? '').trim();
  return /^[a-z0-9]+$/.test(id) ? id : '';
}

function clarityHead(site) {
  const id = clarityId(site);
  if (!id) return '';
  return `<script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "${id}");
</script>`;
}

function headTags(site, landing, base) {
  const title = site.title || site.name;
  const canonical = base ? `${base}/` : undefined;
  const image = absolute(base, site.ogImage);
  const color = site.themeColor ?? {};
  const tags = [
    gtmHead(site),
    clarityHead(site),
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(site.description)}" />`,
    site.keywords?.length ? `<meta name="keywords" content="${esc(site.keywords.join(', '))}" />` : '',
    site.author?.name ? `<meta name="author" content="${esc(site.author.name)}" />` : '',
    `<meta name="robots" content="${ROBOTS}" />`,
    `<meta name="googlebot" content="${ROBOTS}" />`,
    '<meta name="referrer" content="strict-origin-when-cross-origin" />',
    '<meta name="color-scheme" content="light dark" />',
    color.light ? `<meta name="theme-color" media="(prefers-color-scheme: light)" content="${esc(color.light)}" />` : '',
    color.dark ? `<meta name="theme-color" media="(prefers-color-scheme: dark)" content="${esc(color.dark)}" />` : '',
    canonical ? `<link rel="canonical" href="${esc(canonical)}" />` : '',
    canonical ? `<link rel="alternate" hreflang="es" href="${esc(canonical)}" />` : '',
    canonical ? `<link rel="alternate" hreflang="en" href="${esc(canonical.replace(/\/?$/, '/?lang=en'))}" />` : '',
    canonical ? `<link rel="alternate" hreflang="x-default" href="${esc(canonical)}" />` : '',
    site.favicon ? `<link rel="icon" href="./${esc(site.favicon)}" />` : '',
    site.appleTouchIcon ? `<link rel="apple-touch-icon" href="./${esc(site.appleTouchIcon)}" />` : '',
    '<link rel="manifest" href="./site.webmanifest" />',
    '<link rel="author" href="./llms.txt" type="text/plain" />',
    `<meta property="og:type" content="${esc(site.ogType || 'website')}" />`,
    ...Object.entries(site.ogType === 'profile' ? (site.profile ?? {}) : {}).map(
      ([key, value]) => `<meta property="profile:${esc(key)}" content="${esc(value)}" />`,
    ),
    `<meta property="og:locale" content="${esc(site.locale)}" />`,
    '<meta property="og:locale:alternate" content="en_US" />',
    `<meta property="og:site_name" content="${esc(site.name)}" />`,
    canonical ? `<meta property="og:url" content="${esc(canonical)}" />` : '',
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(site.description)}" />`,
    image ? `<meta property="og:image" content="${esc(image)}" />` : '',
    image && /^https:/.test(image) ? `<meta property="og:image:secure_url" content="${esc(image)}" />` : '',
    image && imageType(image) ? `<meta property="og:image:type" content="${imageType(image)}" />` : '',
    image && site.ogImageAlt ? `<meta property="og:image:alt" content="${esc(site.ogImageAlt)}" />` : '',
    image ? `<meta property="og:image:width" content="${esc(site.ogImageWidth || 1200)}" />` : '',
    image ? `<meta property="og:image:height" content="${esc(site.ogImageHeight || 630)}" />` : '',
    '<meta name="twitter:card" content="summary_large_image" />',
    `<meta name="twitter:title" content="${esc(title)}" />`,
    `<meta name="twitter:description" content="${esc(site.description)}" />`,
    image ? `<meta name="twitter:image" content="${esc(image)}" />` : '',
    image && site.ogImageAlt ? `<meta name="twitter:image:alt" content="${esc(site.ogImageAlt)}" />` : '',
    site.twitter ? `<meta name="twitter:creator" content="${esc(site.twitter)}" />` : '',
    site.fonts?.google ? '<link rel="preconnect" href="https://fonts.googleapis.com" />' : '',
    site.fonts?.google ? '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />' : '',
    site.fonts?.google ? `<link rel="stylesheet" href="${esc(site.fonts.google)}" />` : '',
    `<script type="application/ld+json">\n${structuredData(site, landing, base)}\n</script>`,
    `<script>\n${localeScript(site)}\n${themeScript(site)}\n</script>`,
  ];
  return tags.filter(Boolean).join('\n    ');
}

function noscript(site, landing) {
  const hero = heroOf(landing);
  const sections = landing.sections
    .filter((section) => section.type !== 'hero' && section.id && section.title)
    .map((section) => `<li><strong>${esc(plain(section.title))}</strong>${section.lead ? ` — ${esc(plain(section.lead))}` : ''}</li>`)
    .join('\n          ');
  const links = [
    site.repo && `<li><a href="${esc(site.repo)}">Código fuente</a></li>`,
    site.author?.email && `<li><a href="mailto:${esc(site.author.email)}">${esc(site.author.email)}</a></li>`,
    site.whatsapp && `<li><a href="${esc(site.whatsapp)}">WhatsApp</a></li>`,
    site.coffee?.href && `<li><a href="${esc(site.coffee.href)}">${esc(site.coffee.label || 'Invítame un café')}</a></li>`,
  ]
    .filter(Boolean)
    .join('\n          ');

  return `<noscript>
      <main style="font-family: system-ui, sans-serif; max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.6">
        <h1>${esc(plain([hero.title, hero.highlight].filter(Boolean).join(' ')) || site.name)}</h1>
        <p>${esc(plain(hero.lead || site.description))}</p>
        <ul>
          ${sections}
        </ul>
        <ul>
          ${links}
        </ul>
        <p>Activa JavaScript para ver la página completa.</p>
      </main>
    </noscript>`;
}

function sitemap(base) {
  const today = new Date().toISOString().slice(0, 10);
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>${esc(`${base}/`)}</loc>
    <xhtml:link rel="alternate" hreflang="es" href="${esc(`${base}/`)}" />
    <xhtml:link rel="alternate" hreflang="en" href="${esc(`${base}/?lang=en`)}" />
    <xhtml:link rel="alternate" hreflang="x-default" href="${esc(`${base}/`)}" />
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
`;
}

function robots(base) {
  return `User-agent: *
Allow: /

Sitemap: ${base}/sitemap.xml
`;
}

function llms(site, landing, base) {
  const sections = landing.sections
    .filter((section) => section.id && section.title)
    .map((section) => `- [${plain(section.title)}](${base}/#${section.id})${section.lead ? `: ${plain(section.lead)}` : ''}`)
    .join('\n');
  const links = [
    site.repo && `- Código fuente: ${site.repo}`,
    site.author?.name && `- Desarrollado por: ${site.author.name}${site.author.url ? ` (${site.author.url})` : ''}`,
    site.author?.email && `- Contacto: ${site.author.email}`,
    site.author?.telephone && `- Teléfono: ${site.author.telephone}`,
    ...(site.author?.sameAs ?? []).map((link) => `- Perfil: ${link}`),
    site.whatsapp && `- WhatsApp: ${site.whatsapp}`,
    site.coffee?.href && `- ${site.coffee.label || 'Invítame un café'}: ${site.coffee.href}`,
    site.maker?.name && `- Estudio: ${site.maker.name}${site.maker.url ? ` (${site.maker.url})` : ''}`,
  ]
    .filter(Boolean)
    .join('\n');

  const projects = landing.sections
    .filter((section) => section.type === 'projects')
    .flatMap((section) => section.items ?? [])
    .map((item) => {
      const link = (item.actions ?? []).find((action) => /^https?:\/\//.test(action.href));
      return `- ${link ? `[${plain(item.title)}](${link.href})` : plain(item.title)}: ${plain(item.summary)}`;
    })
    .join('\n');

  return `# ${site.name}

${plain(site.description)}

## Secciones

${sections}
${projects ? `\n## Proyectos\n\n${projects}\n` : ''}
## Enlaces

${links}
`;
}

function manifest(site) {
  return JSON.stringify(
    {
      name: site.name,
      short_name: site.shortName || site.name,
      description: site.description,
      lang: site.lang,
      id: './',
      start_url: './',
      scope: './',
      display: 'standalone',
      background_color: site.themeColor?.dark || '#111111',
      theme_color: site.themeColor?.dark || '#111111',
      icons: (site.icons ?? []).map((icon) => ({ purpose: 'any', ...icon })),
    },
    null,
    2,
  );
}

/**
 * Genera el <head>, el <noscript>, sitemap.xml, robots.txt, llms.txt y
 * site.webmanifest a partir de content/site.json y content/landing.json.
 * La URL pública sale de VITE_SITE_URL o, si no está, de site.url.
 */
export function landingFiles({ siteUrl } = {}) {
  let config;
  const load = () => {
    const site = readJson(config.root, 'site.json');
    const landing = readJson(config.root, 'landing.json');
    const base = String(siteUrl || site.url || '').replace(/\/$/, '');
    return { site, landing, base };
  };

  return {
    name: 'kriver-landing-files',
    configResolved(resolved) {
      config = resolved;
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = request.url?.split('?')[0];
        const files = {
          '/robots.txt': ['text/plain', (c) => robots(c.base)],
          '/sitemap.xml': ['application/xml', (c) => sitemap(c.base)],
          '/llms.txt': ['text/plain', (c) => llms(c.site, c.landing, c.base)],
          '/site.webmanifest': ['application/manifest+json', (c) => manifest(c.site)],
        };
        const file = files[path];
        if (!file) return next();
        response.setHeader('Content-Type', `${file[0]}; charset=utf-8`);
        response.end(file[1](load()));
      });
    },
    transformIndexHtml(html) {
      const { site, landing, base } = load();
      return html
        .replaceAll('%LANG%', esc(site.lang || 'es'))
        .replace('<!-- landing:head -->', headTags(site, landing, base))
        .replace('<!-- landing:body -->', gtmBody(site))
        .replace('<!-- landing:noscript -->', noscript(site, landing));
    },
    closeBundle() {
      if (config.command !== 'build') return;
      const { site, landing, base } = load();
      const outDir = resolve(config.root, config.build.outDir);
      writeFileSync(resolve(outDir, 'site.webmanifest'), manifest(site));
      writeFileSync(resolve(outDir, 'llms.txt'), llms(site, landing, base));
      if (base) {
        writeFileSync(resolve(outDir, 'sitemap.xml'), sitemap(base));
        writeFileSync(resolve(outDir, 'robots.txt'), robots(base));
      }
    },
  };
}
