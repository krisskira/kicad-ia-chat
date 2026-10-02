import { useId, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { useI18n } from '../i18n/useI18n';
import { Actions, Paragraphs, Reveal, Rich, Section, SectionHeader } from '../components/ui';
import { focusRing } from '../lib/styles';

function CopyButton({ code }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 font-mono text-xs text-white/60 transition hover:text-white ${focusRing}`}
    >
      {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      {copied ? t('code.copied') : t('code.copy')}
    </button>
  );
}

function CodeWindow({ entry, labelId }) {
  return (
    <Reveal className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-[#0b1020] shadow-card">
      <div className="flex min-h-12 items-center justify-between gap-4 border-b border-white/10 px-4">
        <span id={labelId} className="font-mono text-xs font-semibold text-white/70">
          {entry.commandLabel || entry.label}
        </span>
        <CopyButton code={entry.code} />
      </div>
      <pre aria-labelledby={labelId} className="max-h-130 overflow-auto p-5 font-mono text-[13px] leading-6 text-[#c9d7ff]">
        <code>{entry.code}</code>
      </pre>
      {entry.note ? (
        <p className="border-t border-white/10 px-5 py-4 text-sm leading-relaxed text-white/70 [&_code]:bg-white/10 [&_code]:text-white">
          <Rich text={entry.note} />
        </p>
      ) : null}
    </Reveal>
  );
}

function CodeBlocks({ section }) {
  const baseId = useId();

  return (
    <Section section={section}>
      <SectionHeader section={section} />
      {section.body ? (
        <Reveal className="mt-5 max-w-190 text-lg leading-relaxed text-muted">
          <Paragraphs text={section.body} />
        </Reveal>
      ) : null}
      <div className="mt-14 grid gap-16 lg:gap-20">
        {section.items.map((item, index) => {
          const labelId = `${baseId}-${index}`;
          return (
            <article
              key={item.title}
              className="grid grid-cols-1 items-start gap-7 border-t border-line pt-10 lg:grid-cols-[minmax(0,0.72fr)_minmax(0,1.28fr)] lg:gap-14"
            >
              <Reveal>
                {item.kicker ? (
                  <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-accent">{item.kicker}</p>
                ) : null}
                <h3 className="mt-3 font-display text-2xl font-semibold leading-tight text-fg sm:text-3xl">{item.title}</h3>
                {item.body ? (
                  <div className="mt-4 leading-relaxed text-muted">
                    <Paragraphs text={item.body} />
                  </div>
                ) : null}
              </Reveal>
              <CodeWindow entry={item} labelId={labelId} />
            </article>
          );
        })}
      </div>
      <Actions actions={section.actions} className="mt-12" />
    </Section>
  );
}

function TabbedCode({ section }) {
  const { t } = useI18n();
  const [active, setActive] = useState(0);
  const baseId = useId();
  const tab = section.tabs[active];

  return (
    <Section section={section}>
      <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16">
        <div>
          <SectionHeader section={section} />
          {section.body ? (
            <Reveal className="mt-5 text-lg leading-relaxed text-muted">
              <Paragraphs text={section.body} />
            </Reveal>
          ) : null}
          <Actions actions={section.actions} className="mt-8" />
        </div>
        <Reveal delay={120} className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b1020] shadow-card">
          <div className="flex items-center justify-between gap-4 border-b border-white/10 px-3">
            <div role="tablist" aria-label={t('code.examples')} className="flex overflow-x-auto">
              {section.tabs.map((entry, index) => (
                <button
                  key={entry.label}
                  id={`${baseId}-${index}`}
                  role="tab"
                  type="button"
                  aria-selected={index === active}
                  onClick={() => setActive(index)}
                  className={`shrink-0 border-b-2 px-3 py-3 font-mono text-xs font-semibold transition ${focusRing} ${
                    index === active ? 'border-accent text-white' : 'border-transparent text-white/50 hover:text-white/80'
                  }`}
                >
                  {entry.label}
                </button>
              ))}
            </div>
            <CopyButton code={tab.code} />
          </div>
          <pre role="tabpanel" aria-labelledby={`${baseId}-${active}`} className="max-h-130 overflow-auto p-5 font-mono text-[13px] leading-6 text-[#c9d7ff]">
            <code>{tab.code}</code>
          </pre>
          {tab.note ? (
            <p className="border-t border-white/10 px-5 py-4 text-sm leading-relaxed text-white/70 [&_code]:bg-white/10 [&_code]:text-white">
              <Rich text={tab.note} />
            </p>
          ) : null}
        </Reveal>
      </div>
    </Section>
  );
}

export function Code({ section }) {
  if (section.items?.length) return <CodeBlocks section={section} />;
  return <TabbedCode section={section} />;
}
