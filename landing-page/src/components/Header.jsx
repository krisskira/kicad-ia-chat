import { useEffect, useState } from 'react';
import { Menu, Moon, Sun, X } from 'lucide-react';
import { useI18n } from '../i18n/useI18n';
import { asset, isExternal } from '../lib/content';
import { usePage } from '../lib/usePage';
import { useTheme } from '../theme/context';
import { GitHubIcon, Icon, WhatsAppIcon } from './Icon';
import { focusRing, wrap } from '../lib/styles';

function Logo({ overlay, site }) {
  const { t } = useI18n();
  return (
    <a href="#top" className={`flex items-center gap-3 rounded-md ${focusRing}`} aria-label={t('home.link', { name: site.name })}>
      {site.logo ? <img src={asset(site.logo)} alt="" aria-hidden="true" className="h-9 w-9" /> : null}
      <span className={`whitespace-nowrap font-display text-xl font-semibold tracking-tight ${overlay ? 'text-hero-fg' : 'text-fg'}`}>{site.name}</span>
      {site.badge ? (
        <span className="hidden rounded-full border border-accent/40 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-accent sm:inline">
          {site.badge}
        </span>
      ) : null}
    </a>
  );
}

function LocaleSwitch({ overlay }) {
  const { locale, setLocale, t } = useI18n();
  const next = locale === 'es' ? 'en' : 'es';
  return (
    <button
      type="button"
      onClick={() => setLocale(next)}
      aria-label={next === 'en' ? t('locale.toEn') : t('locale.toEs')}
      className={`inline-flex h-10 min-w-10 items-center justify-center rounded-full px-2 font-mono text-xs font-bold tracking-wide transition ${
        overlay ? 'text-hero-fg hover:bg-white/10' : 'text-fg hover:bg-soft'
      } ${focusRing}`}
    >
      {next.toUpperCase()}
    </button>
  );
}

export function Header() {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const { site, landing } = usePage();
  const [open, setOpen] = useState(false);
  const [atTop, setAtTop] = useState(true);
  const overlay = atTop && !open;
  const tone = overlay ? 'text-hero-fg' : 'text-fg';
  const nav = [
    ...landing.sections.filter((section) => section.nav && section.id).map((section) => ({ label: section.nav, href: `#${section.id}` })),
    ...(site.nav ?? []),
  ];

  useEffect(() => {
    const update = () => setAtTop(window.scrollY < 24);
    update();
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  const iconButton = `inline-flex h-10 w-10 items-center justify-center rounded-full transition ${overlay ? 'text-hero-fg hover:bg-white/10' : 'text-fg hover:bg-soft'} ${focusRing}`;

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-[background-color,box-shadow,backdrop-filter] duration-300 ${
        overlay ? 'bg-transparent' : 'bg-bg/85 shadow-[0_1px_0_var(--line)] backdrop-blur-md'
      }`}
    >
      <div className={`${wrap} flex h-[72px] items-center justify-between gap-6`}>
        <Logo overlay={overlay} site={site} />

        <nav className="hidden items-center gap-8 lg:flex" aria-label={t('menu.main')}>
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              target={isExternal(item.href) ? '_blank' : undefined}
              rel={isExternal(item.href) ? 'noopener noreferrer' : undefined}
              className={`font-sans text-[15px] font-semibold transition hover:text-accent ${tone} ${focusRing}`}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-1">
          {site.repo ? (
            <a href={site.repo} target="_blank" rel="noopener noreferrer" className={iconButton} aria-label={t('source.label')}>
              <GitHubIcon size={20} />
            </a>
          ) : null}
          {site.whatsapp ? (
            <a href={site.whatsapp} target="_blank" rel="noopener noreferrer" className={iconButton} aria-label={t('whatsapp.label')}>
              <WhatsAppIcon size={20} />
            </a>
          ) : null}
          {site.coffee?.href ? (
            <a
              href={site.coffee.href}
              target="_blank"
              rel="noopener noreferrer"
              className={`${iconButton} max-sm:hidden xl:hidden`}
              aria-label={`${site.coffee.label}${t('external')}`}
            >
              <Icon name="coffee" size={20} />
            </a>
          ) : null}
          <LocaleSwitch overlay={overlay} />
          <button type="button" onClick={toggle} className={iconButton} aria-label={theme === 'dark' ? t('theme.light') : t('theme.dark')}>
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          {site.coffee?.href ? (
            <a
              href={site.coffee.href}
              target="_blank"
              rel="noopener noreferrer"
              className={`ml-2 hidden h-10 items-center gap-2 rounded-full border px-4 font-display text-sm font-semibold transition hover:border-accent hover:text-accent xl:inline-flex ${
                overlay ? 'border-hero-fg/25 text-hero-fg' : 'border-line text-fg'
              } ${focusRing}`}
            >
              <Icon name="coffee" size={16} />
              {site.coffee.label}
            </a>
          ) : null}
          {site.cta ? (
            <a
              href={site.cta.href}
              className={`ml-2 hidden h-10 items-center rounded-full bg-accent px-5 font-display text-sm font-semibold text-on-accent transition hover:brightness-110 sm:inline-flex ${focusRing}`}
            >
              {site.cta.label}
            </a>
          ) : null}
          <button
            type="button"
            className={`${iconButton} lg:hidden`}
            aria-expanded={open}
            aria-controls="menu-movil"
            aria-label={open ? t('menu.close') : t('menu.open')}
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="fixed inset-0 top-[72px] z-40 lg:hidden">
          <button className="absolute inset-0 bg-black/40" aria-label={t('menu.close')} onClick={() => setOpen(false)} />
          <nav id="menu-movil" className="absolute inset-x-0 top-0 bg-bg px-5 pb-8 pt-4 shadow-card" aria-label={t('menu.mobile')}>
            <ul className="flex flex-col">
              {nav.map((item) => (
                <li key={item.href}>
                  <a
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={`block border-b border-line/40 py-4 font-display text-lg font-semibold text-fg ${focusRing}`}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
            {site.coffee?.href ? (
              <a
                href={site.coffee.href}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpen(false)}
                className={`mt-6 flex h-12 items-center justify-center gap-2 rounded-full border border-line font-display font-semibold text-fg ${focusRing}`}
              >
                <Icon name="coffee" size={18} />
                {site.coffee.label}
              </a>
            ) : null}
            {site.cta ? (
              <a
                href={site.cta.href}
                onClick={() => setOpen(false)}
                className={`${site.coffee?.href ? 'mt-3' : 'mt-6'} flex h-12 items-center justify-center rounded-full bg-accent font-display font-semibold text-on-accent ${focusRing}`}
              >
                {site.cta.label}
              </a>
            ) : null}
          </nav>
        </div>
      ) : null}
    </header>
  );
}
