import { useId, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { useI18n } from '../i18n/useI18n';
import { Actions, Paragraphs, Reveal, Section, SectionHeader } from '../components/ui';
import { focusRing } from '../lib/styles';

export function Code({ section }) {
  const { t } = useI18n();
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);
  const baseId = useId();
  const tab = section.tabs[active];

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(tab.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Section section={section}>
      <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16">
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
            <button
              type="button"
              onClick={copy}
              className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 font-mono text-xs text-white/60 transition hover:text-white ${focusRing}`}
            >
              {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
              {copied ? t('code.copied') : t('code.copy')}
            </button>
          </div>
          <pre role="tabpanel" aria-labelledby={`${baseId}-${active}`} className="max-h-[520px] overflow-auto p-5 font-mono text-[13px] leading-6 text-[#c9d7ff]">
            <code>{tab.code}</code>
          </pre>
        </Reveal>
      </div>
    </Section>
  );
}
