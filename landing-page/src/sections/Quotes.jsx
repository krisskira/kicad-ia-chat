import { Quote } from 'lucide-react';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

export function Quotes({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <ul className="mt-12 grid gap-6 lg:mt-14 lg:grid-cols-2">
        {section.items.map((item, index) => (
          <Reveal as="li" key={item.author} delay={(index % 2) * 90} className="flex flex-col rounded-2xl border border-line/60 bg-card p-6 lg:p-8">
            <Quote size={28} aria-hidden="true" className="text-accent" />
            <blockquote className="mt-4 flex-1 text-lg leading-relaxed text-fg">
              <p>
                <Rich text={item.text} />
              </p>
            </blockquote>
            <p className="mt-6 text-sm">
              <span className="font-display font-semibold text-fg">{item.author}</span>
              {item.role ? <span className="text-muted"> · {item.role}</span> : null}
            </p>
          </Reveal>
        ))}
      </ul>
    </Section>
  );
}
