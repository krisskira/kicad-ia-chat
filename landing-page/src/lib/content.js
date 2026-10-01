import rawSite from '../../content/site.json';
import rawLanding from '../../content/landing.json';

const ENV_TOKEN = /\{\{(VITE_[A-Z0-9_]+)\}\}/g;
const DROP = Symbol('drop');

// "{{VITE_APP_URL}}/login" toma la variable del .env en el build. Si falta,
// el objeto que tiene ese href (botón, enlace) desaparece en vez de quedar roto.
function resolveEnv(value, key) {
  if (typeof value === 'string') {
    let missing = false;
    const out = value.replace(ENV_TOKEN, (_, name) => {
      const found = import.meta.env[name];
      if (!found) missing = true;
      return (found ?? '').replace(/\/$/, '');
    });
    return missing && key === 'href' ? DROP : out;
  }
  if (Array.isArray(value)) {
    return value.map((item) => resolveEnv(item)).filter((item) => item !== DROP);
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).map(([k, v]) => [k, resolveEnv(v, k)]);
    if (entries.some(([, v]) => v === DROP)) return DROP;
    return Object.fromEntries(entries);
  }
  return value;
}

export const site = resolveEnv(rawSite);
export const landing = resolveEnv(rawLanding);

export function asset(path) {
  if (!path) return undefined;
  if (/^(https?:|data:|blob:)/.test(path)) return path;
  return `${import.meta.env.BASE_URL}${path.replace(/^\.?\//, '')}`;
}

export function isExternal(href) {
  return /^https?:\/\//.test(href ?? '');
}
