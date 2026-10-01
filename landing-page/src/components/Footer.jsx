import { ArrowUp, Mail } from 'lucide-react';
import { useI18n } from '../i18n/useI18n';
import { asset, isExternal } from '../lib/content';
import { usePage } from '../lib/usePage';
import { BrandBar, Rich } from './ui';
import { focusRing, wrap } from '../lib/styles';
import { GitHubIcon, WhatsAppIcon } from './Icon';

const linkClass = `rounded-sm text-hero-fg/70 transition hover:text-accent ${focusRing}`;

function FooterLink({ link }) {
  const external = isExternal(link.href);
  return (
    <a href={link.href} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer' : undefined} className={linkClass}>
      {link.label}
    </a>
  );
}

export function Footer() {
  const { t } = useI18n();
  const { site } = usePage();
  const footer = site.footer ?? {};
  const year = new Date().getFullYear();

  return (
    <footer className="relative overflow-hidden bg-hero text-hero-fg">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-40 -top-40 h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle,var(--glow-1),transparent_65%)]"
      />
      <div className={`${wrap} relative grid gap-12 py-16 md:grid-cols-2 lg:grid-cols-[1.6fr_1fr_1fr] lg:py-20`}>
        <div className="max-w-[420px]">
          <a href="#top" className={`inline-flex items-center gap-3 rounded-md ${focusRing}`}>
            {site.logo ? <img src={asset(site.logo)} alt="" aria-hidden="true" className="h-10 w-10" /> : null}
            <span className="font-display text-2xl font-semibold">{site.name}</span>
          </a>
          {footer.text ? (
            <p className="mt-5 leading-relaxed text-hero-fg/70">
              <Rich text={footer.text} />
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-3">
            {site.repo ? (
              <a
                href={site.repo}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex h-11 items-center gap-2 rounded-full border border-hero-fg/20 px-4 text-sm font-semibold transition hover:border-accent hover:text-accent ${focusRing}`}
              >
                <GitHubIcon size={18} />
                GitHub
              </a>
            ) : null}
            {site.author?.email ? (
              <a
                href={`mailto:${site.author.email}`}
                className={`inline-flex h-11 items-center gap-2 rounded-full border border-hero-fg/20 px-4 text-sm font-semibold transition hover:border-accent hover:text-accent ${focusRing}`}
              >
                <Mail size={18} aria-hidden="true" />
                {site.author.email}
              </a>
            ) : null}
            {site.whatsapp ? (
              <a
                href={site.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex h-11 items-center gap-2 rounded-full border border-hero-fg/20 px-4 text-sm font-semibold transition hover:border-accent hover:text-accent ${focusRing}`}
              >
                <WhatsAppIcon size={18} />
                WhatsApp
              </a>
            ) : null}
          </div>
        </div>

        {(footer.columns ?? []).map((column) => (
          <nav key={column.title} aria-label={column.title}>
            <h2 className="font-display text-base font-semibold">
              {column.title}
              <BrandBar className="mt-3" />
            </h2>
            <ul className="mt-6 grid gap-3 text-[15px]">
              {column.links.map((link) => (
                <li key={link.href + link.label}>
                  <FooterLink link={link} />
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="relative border-t border-hero-fg/10">
        <div className={`${wrap} flex flex-col items-center gap-4 py-6 text-center text-sm text-hero-fg/60 md:flex-row md:justify-between md:text-left`}>
          <p>
            © {year} {footer.rights || site.name}
            {site.maker ? (
              <>
                {` · ${t('footer.by')} `}
                <a href={site.maker.url} target="_blank" rel="noopener noreferrer" className={`font-semibold text-hero-fg/80 ${linkClass}`}>
                  {site.maker.name}
                </a>
              </>
            ) : null}
          </p>
          <a href="#top" className={`group inline-flex items-center gap-2 font-semibold text-hero-fg transition hover:text-accent ${focusRing}`}>
            {t('footer.top')}
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-hero-fg/25 transition group-hover:-translate-y-0.5 group-hover:border-accent">
              <ArrowUp size={16} aria-hidden="true" />
            </span>
          </a>
        </div>
      </div>
      <div className="grid h-1.5 grid-cols-3" aria-hidden="true">
        <span className="bg-accent" />
        <span className="bg-accent-2" />
        <span className="bg-accent-3" />
      </div>
    </footer>
  );
}
