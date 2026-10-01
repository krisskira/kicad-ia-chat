import { Icon } from '../components/Icon';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

const columns = {
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-2 lg:grid-cols-3',
  4: 'md:grid-cols-2 lg:grid-cols-4',
};

export function Features({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <ul className={`mt-12 grid gap-5 lg:mt-16 ${columns[section.columns] || columns[3]}`}>
        {section.items.map((item, index) => (
          <Reveal as="li" key={item.title} delay={(index % 3) * 80} className="group relative rounded-2xl border border-line/60 bg-card p-6 transition hover:-translate-y-1 hover:border-accent/60 hover:shadow-card">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-accent/12 text-accent ring-1 ring-accent/25">
              <Icon name={item.icon} size={22} />
            </span>
            <h3 className="mt-5 font-display text-lg font-semibold text-fg">{item.title}</h3>
            <p className="mt-2 leading-relaxed text-muted">
              <Rich text={item.text} />
            </p>
          </Reveal>
        ))}
      </ul>
    </Section>
  );
}
