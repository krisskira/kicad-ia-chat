import { Actions, Reveal, Rich, Section } from '../components/ui';

export function Cta({ section }) {
  return (
    <Section section={section}>
      <Reveal className="relative overflow-hidden rounded-3xl bg-hero px-6 py-14 text-center text-hero-fg sm:px-12 lg:py-20">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 -top-24 h-[380px] w-[380px] rounded-full bg-[radial-gradient(circle,var(--glow-1),transparent_65%)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -right-24 h-[420px] w-[420px] rounded-full bg-[radial-gradient(circle,var(--glow-2),transparent_65%)]"
        />
        <div className="relative mx-auto max-w-[720px]">
          <h2 id={`${section.id}-title`} className="font-display text-3xl font-semibold leading-tight sm:text-4xl lg:text-[44px]">
            <Rich text={section.title} />
          </h2>
          {section.lead ? (
            <p className="mt-5 text-lg leading-relaxed text-hero-fg/75">
              <Rich text={section.lead} />
            </p>
          ) : null}
          <Actions actions={section.actions} tone="hero" className="mt-9 justify-center" />
        </div>
      </Reveal>
    </Section>
  );
}
