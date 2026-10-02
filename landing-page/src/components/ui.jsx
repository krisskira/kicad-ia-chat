import { useEffect, useRef, useState } from 'react';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { Icon } from './Icon';
import { useI18n } from '../i18n/useI18n';
import { isExternal } from '../lib/content';
import { focusRing, wrap } from '../lib/styles';

/** Texto con **negrita** y `código` en línea. */
export function Rich({ text }) {
  if (!text) return null;
  return String(text)
    .split(/(\*\*.+?\*\*|`.+?`)/g)
    .map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-semibold text-fg">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={index} className="rounded bg-soft px-1.5 py-0.5 font-mono text-[0.88em] text-fg [overflow-wrap:anywhere]">
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
}

export function Paragraphs({ text, className = '' }) {
  const items = Array.isArray(text) ? text : text ? [text] : [];
  return items.map((item, index) => (
    <p key={index} className={`${index ? 'mt-4' : ''} ${className}`}>
      <Rich text={item} />
    </p>
  ));
}

export function BrandBar({ className = '' }) {
  return (
    <span className={`flex gap-1 ${className}`} aria-hidden="true">
      <span className="h-1 w-6 rounded-full bg-accent" />
      <span className="h-1 w-6 rounded-full bg-accent-2" />
      <span className="h-1 w-6 rounded-full bg-accent-3" />
    </span>
  );
}

function useReveal() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || visible) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '0px 0px -10% 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [visible]);

  return [ref, visible];
}

export function Reveal({ as = 'div', delay = 0, className = '', children, ...props }) {
  const Tag = as;
  const [ref, visible] = useReveal();
  return (
    <Tag
      ref={ref}
      className={`reveal ${visible ? 'is-visible' : ''} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
      {...props}
    >
      {children}
    </Tag>
  );
}

export function Section({ section, className = '', children }) {
  const alt = section.tone === 'alt';
  return (
    <section
      id={section.id}
      aria-labelledby={section.title ? `${section.id}-title` : undefined}
      className={`relative overflow-x-clip py-20 lg:py-28 ${alt ? 'bg-bg-alt' : ''} ${className}`}
    >
      <div className={wrap}>{children}</div>
    </section>
  );
}

export function SectionHeader({ section, align = 'left', className = '' }) {
  const centered = align === 'center';
  return (
    <Reveal className={`${centered ? 'mx-auto text-center' : ''} max-w-[760px] ${className}`}>
      {section.kicker ? (
        <p className={`flex items-center gap-3 font-sans text-sm font-semibold uppercase tracking-[0.18em] text-accent ${centered ? 'justify-center' : ''}`}>
          <BrandBar />
          {section.kicker}
        </p>
      ) : null}
      {section.title ? (
        <h2 id={`${section.id}-title`} className="mt-4 font-display text-3xl font-semibold leading-tight tracking-[-0.01em] text-fg sm:text-4xl lg:text-[44px]">
          <Rich text={section.title} />
        </h2>
      ) : null}
      {section.lead ? (
        <p className="mt-5 text-lg leading-relaxed text-muted lg:text-xl">
          <Rich text={section.lead} />
        </p>
      ) : null}
    </Reveal>
  );
}

const buttonBase = `group inline-flex items-center justify-center gap-2 rounded-full font-display text-base font-semibold transition ${focusRing}`;
const buttonBox = 'h-12 px-6 max-sm:w-full';

const buttonVariants = {
  primary: `${buttonBox} bg-accent text-on-accent shadow-[0_10px_30px_-12px_var(--accent)] hover:brightness-110`,
  secondary: `${buttonBox} border border-line text-fg hover:border-accent hover:text-accent`,
  hero: `${buttonBox} border border-hero-fg/30 text-hero-fg hover:border-hero-fg hover:bg-hero-fg/10`,
  link: 'text-accent underline-offset-4 hover:underline',
};

export function ActionLink({ action, tone }) {
  const { t } = useI18n();
  const external = isExternal(action.href);
  const variant = action.variant === 'secondary' && tone === 'hero' ? 'hero' : action.variant || 'primary';
  const TrailingIcon = external ? ArrowUpRight : ArrowRight;
  return (
    <a
      href={action.href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      className={`${buttonBase} ${buttonVariants[variant]}`}
    >
      {action.icon ? <Icon name={action.icon} size={18} /> : null}
      {action.label}
      {external ? <span className="sr-only">{t('external')}</span> : null}
      {action.icon ? null : (
        <TrailingIcon size={18} aria-hidden="true" className="transition group-hover:translate-x-0.5" />
      )}
    </a>
  );
}

export function Actions({ actions, tone, className = '' }) {
  if (!actions?.length) return null;
  return (
    <div className={`flex flex-wrap items-center gap-4 ${className}`}>
      {actions.map((action) => (
        <ActionLink key={action.href + action.label} action={action} tone={tone} />
      ))}
    </div>
  );
}
