import { ChevronDown } from 'lucide-react';
import { Media } from '../components/Media';
import { Actions, Rich } from '../components/ui';
import { focusRing, wrap } from '../lib/styles';

export function Hero({ section }) {
  return (
    <section id="top" aria-labelledby="hero-title" className="relative flex min-h-[100svh] flex-col overflow-hidden bg-hero pt-[72px] text-hero-fg">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-48 -top-48 h-[620px] w-[620px] rounded-full bg-[radial-gradient(circle,var(--glow-1),transparent_65%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-40 bottom-[-240px] h-[680px] w-[680px] rounded-full bg-[radial-gradient(circle,var(--glow-2),transparent_65%)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(var(--hero-fg)_1px,transparent_1px),linear-gradient(90deg,var(--hero-fg)_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black,transparent_75%)]"
      />

      <div className={`${wrap} relative grid flex-1 items-center gap-12 pb-16 pt-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-14 lg:pb-24`}>
        <div className="max-w-[620px]">
          {section.badge ? (
            <p className="inline-flex items-center gap-2 rounded-full border border-hero-fg/15 bg-hero-fg/5 px-4 py-1.5 text-xs font-semibold tracking-wide text-hero-fg/90 sm:text-sm">
              <span className="relative flex h-2 w-2" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full rounded-full bg-accent opacity-75 motion-safe:animate-ping" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              {section.badge}
            </p>
          ) : null}

          <h1 id="hero-title" className="mt-6 font-display text-[36px] font-semibold leading-[1.1] tracking-[-0.02em] sm:text-5xl lg:text-[58px]">
            <Rich text={section.title} /> {section.highlight ? <span className="text-gradient">{section.highlight}</span> : null}
          </h1>

          {section.lead ? (
            <p className="mt-6 max-w-[560px] text-lg leading-[1.5] text-hero-fg/75 lg:text-xl">
              <Rich text={section.lead} />
            </p>
          ) : null}

          <Actions actions={section.actions} tone="hero" className="mt-9" />

          {section.stats?.length ? (
            <dl className="mt-10 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-hero-fg/10 pt-6 sm:grid-cols-4">
              {section.stats.map((stat) => (
                <div key={stat.label} className="flex flex-col gap-1">
                  <dt className="order-2 text-xs leading-snug text-hero-fg/60">{stat.label}</dt>
                  <dd className="font-display text-2xl font-semibold text-hero-fg">{stat.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>

        {section.media ? (
          <div
            className={`relative motion-safe:animate-[float_9s_ease-in-out_infinite] ${
              section.media.portrait ? 'mx-auto w-full max-w-[200px] sm:max-w-[280px] lg:max-w-[400px] max-lg:order-first' : ''
            }`}
          >
            <Media media={section.media} priority />
          </div>
        ) : null}
      </div>

      {section.next ? (
        <a
          href={section.next.href}
          className={`absolute bottom-6 left-1/2 hidden -translate-x-1/2 flex-col items-center gap-1 rounded-md text-xs font-semibold text-hero-fg/60 transition hover:text-hero-fg xl:flex ${focusRing}`}
        >
          {section.next.label}
          <ChevronDown size={20} aria-hidden="true" className="motion-safe:animate-bounce" />
        </a>
      ) : null}

      <div className="relative h-1.5" aria-hidden="true">
        <div className="grid h-full grid-cols-3">
          <span className="bg-accent shadow-[0_0_14px_2px_var(--accent)]" />
          <span className="bg-accent-2 shadow-[0_0_14px_2px_var(--accent-2)]" />
          <span className="bg-accent-3 shadow-[0_0_14px_2px_var(--accent-3)]" />
        </div>
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <span className="absolute inset-y-0 left-0 w-1/5 bg-[linear-gradient(90deg,transparent,rgba(255,255,255,.95),transparent)] mix-blend-screen motion-safe:animate-sweep motion-reduce:hidden" />
        </div>
      </div>
    </section>
  );
}
