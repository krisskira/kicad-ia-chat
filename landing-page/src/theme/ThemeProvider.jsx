import { useEffect, useState } from 'react';
import { site } from '../lib/content';
import { ThemeContext } from './context';

const STORAGE_KEY = `${site.slug || 'landing'}-theme`;

function getInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  const fallback = site.defaultTheme || 'system';
  if (fallback !== 'system') return fallback;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
    const color = site.themeColor?.[theme];
    if (color) document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => meta.setAttribute('content', color));
  }, [theme]);

  const toggle = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'));

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}
