import { useEffect, useMemo, useState } from 'react';
import { site } from '../lib/content';
import { LocaleContext } from './context';
import { translate } from './messages';

const STORAGE_KEY = `${site.slug || 'landing'}-locale`;

function readLocale() {
  const fromUrl = new URLSearchParams(window.location.search).get('lang');
  if (fromUrl === 'en' || fromUrl === 'es') return fromUrl;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'es') return stored;
  return navigator.language?.toLowerCase().startsWith('en') ? 'en' : 'es';
}

export function LocaleProvider({ children }) {
  const [locale, setLocale] = useState(readLocale);
  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: (key, vars) => translate(locale, key, vars),
    }),
    [locale],
  );

  useEffect(() => {
    document.documentElement.lang = locale === 'en' ? 'en' : site.lang || 'es';
    localStorage.setItem(STORAGE_KEY, locale);
    const url = new URL(window.location.href);
    if (url.searchParams.get('lang') !== locale) {
      url.searchParams.set('lang', locale);
      window.history.replaceState(window.history.state, '', url);
    }
  }, [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
