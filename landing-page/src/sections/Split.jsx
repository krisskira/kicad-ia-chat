import { Check } from 'lucide-react';
import { Media } from '../components/Media';
import { Actions, BrandBar, Paragraphs, Reveal, Rich, Section } from '../components/ui';

export function Split({ section }) {
  return (
    <Section section={section}>
      <div className={`grid items-center gap-12 lg:grid-cols-2 lg:gap-16 ${section.reverse ? 'lg:[&>*:first-child]:order-2' : ''}`}>
        <Reveal>
          {section.kicker ? (
            <p className="flex items-center gap-3 text-sm font-semibold uppercase tracking-[0.18em] text-accent">
              <BrandBar />
              {section.kicker}
            </p>
          ) : null}
          <h2 id={`${section.id}-title`} className="mt-4 font-display text-3xl font-semibold leading-tight tracking-[-0.01em] text-fg sm:text-4xl">
            <Rich text={section.title} />
          </h2>
          <div className="mt-5 text-lg leading-relaxed text-muted">
            <Paragraphs text={section.body ?? section.lead} />
          </div>
          {section.bullets?.length ? (
            <ul className="mt-7 grid gap-3">
              {section.bullets.map((bullet) => (
                <li key={bullet} className="flex items-start gap-3 text-fg">
                  <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
                    <Check size={14} strokeWidth={3} aria-hidden="true" />
                  </span>
                  <span className="leading-relaxed">
                    <Rich text={bullet} />
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <Actions actions={section.actions} className="mt-8" />
        </Reveal>
        <Reveal delay={120}>
          <Media media={section.media} />
        </Reveal>
      </div>
    </Section>
  );
}
