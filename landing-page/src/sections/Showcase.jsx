import { useId, useState } from 'react';
import { Media } from '../components/Media';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';
import { focusRing } from '../lib/styles';

export function Showcase({ section }) {
  const [active, setActive] = useState(0);
  const baseId = useId();
  const item = section.items[active];

  const onKeyDown = (event) => {
    const last = section.items.length - 1;
    const next = { ArrowRight: active + 1, ArrowLeft: active - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const index = (next + section.items.length) % section.items.length;
    setActive(index);
    document.getElementById(`${baseId}-tab-${index}`)?.focus();
  };

  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <Reveal className="mt-10 lg:mt-14">
        <div role="tablist" aria-label={section.title} className="flex gap-2 overflow-x-auto pb-2" onKeyDown={onKeyDown}>
          {section.items.map((entry, index) => (
            <button
              key={entry.label}
              id={`${baseId}-tab-${index}`}
              role="tab"
              type="button"
              aria-selected={index === active}
              aria-controls={`${baseId}-panel`}
              tabIndex={index === active ? 0 : -1}
              onClick={() => setActive(index)}
              className={`shrink-0 rounded-full px-5 py-2.5 text-sm font-semibold transition ${focusRing} ${
                index === active ? 'bg-accent text-on-accent' : 'border border-line/60 text-muted hover:border-accent hover:text-fg'
              }`}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <div
          id={`${baseId}-panel`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${active}`}
          className={`mt-6 grid items-start gap-8 ${item.text ? 'lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]' : ''}`}
        >
          <Media key={item.media.src} media={item.media} />
          {item.text ? (
            <div className="lg:pt-4">
              <h3 className="font-display text-2xl font-semibold text-fg">{item.title || item.label}</h3>
              <p className="mt-3 text-lg leading-relaxed text-muted">
                <Rich text={item.text} />
              </p>
            </div>
          ) : null}
        </div>
      </Reveal>
    </Section>
  );
}
