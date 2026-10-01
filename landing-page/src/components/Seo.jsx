import { useEffect } from 'react';
import { useI18n } from '../i18n/useI18n';
import { usePage } from '../lib/usePage';

function setMeta(selector, content) {
  const element = document.querySelector(selector);
  if (element && content) element.setAttribute('content', content);
}

// El HTML estático sale en español. Al cambiar de idioma se actualizan el
// título y las metas que el navegador y las previsualizaciones leen.
export function Seo() {
  const { locale } = useI18n();
  const { site } = usePage();

  useEffect(() => {
    const title = site.title || site.name;
    document.title = title;
    setMeta('meta[name="description"]', site.description);
    setMeta('meta[name="keywords"]', site.keywords?.join(', '));
    setMeta('meta[property="og:title"]', title);
    setMeta('meta[property="og:description"]', site.description);
    setMeta('meta[property="og:locale"]', locale === 'en' ? 'en_US' : site.locale);
    setMeta('meta[property="og:image:alt"]', site.ogImageAlt);
    setMeta('meta[name="twitter:title"]', title);
    setMeta('meta[name="twitter:description"]', site.description);
  }, [locale, site]);

  return null;
}
