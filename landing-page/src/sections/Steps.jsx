import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

const columns = { 3: 'lg:grid-cols-3', 4: 'lg:grid-cols-4', 5: 'lg:grid-cols-3 xl:grid-cols-5', 6: 'lg:grid-cols-3' };

export function Steps({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <ol className={`mt-12 grid gap-6 md:grid-cols-2 lg:mt-16 ${columns[section.items.length] || ''}`}>
        {section.items.map((item, index) => (
          <Reveal as="li" key={item.title} delay={index * 90} className="relative rounded-2xl border border-line/60 bg-card p-6">
            <span className="font-mono text-sm font-semibold text-accent">{String(index + 1).padStart(2, '0')}</span>
            <span aria-hidden="true" className="mt-3 block h-px w-full bg-[linear-gradient(90deg,var(--accent),transparent)]" />
            <h3 className="mt-5 font-display text-lg font-semibold text-fg">{item.title}</h3>
            <p className="mt-2 leading-relaxed text-muted">
              <Rich text={item.text} />
            </p>
          </Reveal>
        ))}
      </ol>
    </Section>
  );
}
