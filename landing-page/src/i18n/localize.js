import catalog from '../../content/en.json';

// El español de content/ es la fuente. En inglés, cada texto se busca tal cual
// en content/en.json. Lo que no esté se queda en español.
const KEEP = new Set([
  'slug',
  'id',
  'icon',
  'href',
  'to',
  'src',
  'poster',
  'frame',
  'type',
  'variant',
  'tone',
  'align',
  'lang',
  'locale',
  'url',
  'logo',
  'favicon',
  'ogImage',
  'repo',
  'width',
  'height',
  'columns',
  'defaultTheme',
  '@type',
  '@id',
  'applicationCategory',
  'schema',
]);

function keepAsIs(key, value) {
  // "columns" es un número en las secciones y una lista de enlaces en el footer.
  if (key === 'columns') return typeof value === 'number';
  if (KEEP.has(key)) return true;
  return (
    typeof value === 'string' &&
    (/^https?:/.test(value) ||
      value.startsWith('/') ||
      /^\+\d[\d\s()-]{6,}$/.test(value) ||
      value.startsWith('media/') ||
      value.startsWith('{{') ||
      value.includes('@') ||
      /^#[0-9a-fA-F]{3,8}$/.test(value))
  );
}

function isLocaleMessage(value) {
  const keys = Object.keys(value);
  return keys.length === 2 && typeof value.es === 'string' && typeof value.en === 'string';
}

export function localize(value, locale) {
  if (Array.isArray(value)) return value.map((item) => localize(item, locale));
  if (value && typeof value === 'object') {
    if (isLocaleMessage(value)) return value[locale] || value.es;
    return Object.fromEntries(
      Object.entries(value).map(([childKey, item]) => [childKey, keepAsIs(childKey, item) ? item : localize(item, locale)]),
    );
  }
  if (typeof value === 'string' && locale === 'en') return catalog[value] ?? value;
  return value;
}
