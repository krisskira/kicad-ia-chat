export const messages = {
  es: {
    'skip': 'Saltar al contenido',
    'locale.toEn': 'Cambiar el sitio a inglés',
    'locale.toEs': 'Cambiar el sitio a español',
    'theme.dark': 'Activar modo oscuro',
    'theme.light': 'Activar modo claro',
    'menu.open': 'Abrir menú',
    'menu.close': 'Cerrar menú',
    'menu.main': 'Principal',
    'menu.mobile': 'Móvil',
    'home.link': '{name}, ir al inicio',
    'source.label': 'Código fuente (se abre en una pestaña nueva)',
    'whatsapp.label': 'WhatsApp (se abre en una pestaña nueva)',
    'external': ' (se abre en una pestaña nueva)',
    'footer.by': 'Un proyecto de',
    'footer.top': 'Volver arriba',
    'code.examples': 'Ejemplos',
    'code.copy': 'Copiar',
    'code.copied': 'Copiado',
  },
  en: {
    'skip': 'Skip to content',
    'locale.toEn': 'Switch the site to English',
    'locale.toEs': 'Switch the site to Spanish',
    'theme.dark': 'Switch to dark mode',
    'theme.light': 'Switch to light mode',
    'menu.open': 'Open menu',
    'menu.close': 'Close menu',
    'menu.main': 'Main',
    'menu.mobile': 'Mobile',
    'home.link': '{name}, go to home',
    'source.label': 'Source code (opens in a new tab)',
    'whatsapp.label': 'WhatsApp (opens in a new tab)',
    'external': ' (opens in a new tab)',
    'footer.by': 'A project by',
    'footer.top': 'Back to top',
    'code.examples': 'Examples',
    'code.copy': 'Copy',
    'code.copied': 'Copied',
  },
};

export function translate(locale, key, vars) {
  const template = messages[locale]?.[key] ?? messages.es[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name) => vars[name] ?? '');
}
