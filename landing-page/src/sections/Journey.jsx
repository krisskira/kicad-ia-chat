import { ArrowDown } from 'lucide-react';
import { Paragraphs, Reveal, Rich, Section, SectionHeader } from '../components/ui';

const dots = ['border-accent', 'border-accent-2', 'border-accent-3'];

export function Journey({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <ol className="relative mt-14 lg:mt-20">
        <span
          aria-hidden="true"
          className="absolute bottom-0 left-[7px] top-2 w-px md:top-10 bg-[linear-gradient(var(--accent),var(--accent-2),var(--accent-3))] opacity-70 md:left-[227px]"
        />
        {section.items.map((item, index) => (
          <li key={item.title} className="relative grid gap-3 pb-10 last:pb-0 md:grid-cols-[180px_minmax(0,1fr)] md:gap-10">
            <span
              aria-hidden="true"
              className={`absolute left-0 top-0.5 z-10 h-4 w-4 rounded-full border-[3px] bg-bg md:left-[220px] md:top-8 ${dots[index % dots.length]}`}
            />
            <Reveal className="pl-8 md:sticky md:top-28 md:self-start md:pl-0 md:pt-7 md:text-right">
              <p className="font-mono text-sm font-semibold text-accent">{item.period}</p>
              {item.place ? <p className="mt-1 text-sm leading-snug text-muted">{item.place}</p> : null}
            </Reveal>

            <div className="relative pl-8 md:pl-10">
              <Reveal delay={80} className="rounded-2xl border border-line/60 bg-card p-6 shadow-[0_1px_0_var(--line)] lg:p-8">
                {item.label ? (
                  <p className="font-sans text-xs font-semibold uppercase tracking-[0.18em] text-muted">{item.label}</p>
                ) : null}
                <h3 className="mt-2 font-display text-2xl font-semibold leading-snug text-fg">
                  <Rich text={item.title} />
                </h3>
                <div className="mt-4 text-[17px] leading-relaxed text-muted">
                  <Paragraphs text={item.body} />
                </div>
                {item.takeaway ? (
                  <div className="mt-6 rounded-xl border-l-4 border-accent bg-soft px-5 py-4">
                    {item.takeaway.label ? (
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{item.takeaway.label}</p>
                    ) : null}
                    <p className="mt-1 leading-relaxed text-fg">
                      <Rich text={item.takeaway.text} />
                    </p>
                  </div>
                ) : null}
              </Reveal>
              {item.next ? (
                <Reveal delay={140} as="p" className="mt-5 flex items-start gap-3 text-[15px] italic leading-relaxed text-muted">
                  <ArrowDown size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-accent" />
                  <Rich text={item.next} />
                </Reveal>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
