import { Media } from '../components/Media';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

export function Stats({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <dl className="mt-12 grid gap-5 sm:grid-cols-2 lg:mt-14 lg:grid-cols-4">
        {section.items.map((item, index) => (
          <Reveal key={item.label} delay={index * 80} className="flex flex-col rounded-2xl border border-line/60 bg-card p-6">
            <dt className="order-2 mt-2 font-semibold text-fg">{item.label}</dt>
            <dd className="order-1 font-display text-4xl font-semibold tracking-tight text-accent">
              {item.value}
              {item.unit ? <span className="ml-1 text-xl text-muted">{item.unit}</span> : null}
            </dd>
            {item.note ? (
              <dd className="order-3 mt-2 text-sm leading-relaxed text-muted">
                <Rich text={item.note} />
              </dd>
            ) : null}
          </Reveal>
        ))}
      </dl>
      {section.media ? (
        <Reveal className="mt-12">
          <Media media={section.media} />
        </Reveal>
      ) : null}
    </Section>
  );
}
