import { Plus } from 'lucide-react';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

export function Faq({ section }) {
  return (
    <Section section={section}>
      <div className="grid gap-12 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-16">
        <SectionHeader section={section} />
        <Reveal className="divide-y divide-line/50 border-y border-line/50">
          {section.items.map((item) => (
            <details key={item.q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-start justify-between gap-6 font-display text-lg font-semibold text-fg marker:hidden [&::-webkit-details-marker]:hidden">
                {item.q}
                <Plus size={20} aria-hidden="true" className="mt-1 shrink-0 text-accent transition group-open:rotate-45" />
              </summary>
              <p className="mt-3 leading-relaxed text-muted">
                <Rich text={item.a} />
              </p>
            </details>
          ))}
        </Reveal>
      </div>
    </Section>
  );
}
