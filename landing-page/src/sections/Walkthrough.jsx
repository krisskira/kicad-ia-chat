import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { Media } from '../components/Media';
import { Reveal, Rich, Section, SectionHeader } from '../components/ui';
import { useI18n } from '../i18n/useI18n';
import { asset } from '../lib/content';
import { focusRing } from '../lib/styles';

const DEFAULT_SECONDS = 7;
const NO_STEPS = [];

const control = `inline-flex h-11 w-11 items-center justify-center rounded-full border border-line text-fg transition hover:border-accent hover:text-accent disabled:pointer-events-none disabled:opacity-40 ${focusRing}`;

function Tabs({ baseId, view, setView, hasVideo }) {
  const { t } = useI18n();
  if (!hasVideo) return null;
  const tabs = [
    ['steps', t('walkthrough.steps')],
    ['video', t('walkthrough.video')],
  ];
  const onKeyDown = (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const next = view === 'steps' ? 'video' : 'steps';
    setView(next);
    document.getElementById(`${baseId}-tab-${next}`)?.focus();
  };
  return (
    <div role="tablist" aria-label={t('walkthrough.views')} className="inline-flex rounded-full border border-line bg-card p-1" onKeyDown={onKeyDown}>
      {tabs.map(([id, label]) => (
        <button
          key={id}
          id={`${baseId}-tab-${id}`}
          type="button"
          role="tab"
          aria-selected={view === id}
          aria-controls={`${baseId}-panel-${id}`}
          tabIndex={view === id ? 0 : -1}
          onClick={() => setView(id)}
          className={`h-10 rounded-full px-5 font-display text-sm font-semibold transition ${focusRing} ${
            view === id ? 'bg-accent text-on-accent' : 'text-muted hover:text-fg'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function Steps({ baseId, section }) {
  const { t } = useI18n();
  const steps = section.steps ?? NO_STEPS;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const step = steps[index];
  const last = steps.length - 1;
  const listRef = useRef(null);

  const move = useCallback((delta) => setIndex((value) => Math.max(0, Math.min(last, value + delta))), [last]);

  useEffect(() => {
    if (!playing || index >= last) return undefined;
    const seconds = steps[index]?.seconds ?? section.seconds ?? DEFAULT_SECONDS;
    const timer = window.setTimeout(() => {
      setIndex(index + 1);
      if (index + 1 >= last) setPlaying(false);
    }, seconds * 1000);
    return () => window.clearTimeout(timer);
  }, [playing, index, last, steps, section.seconds]);

  useEffect(() => {
    const next = steps[index + 1]?.media?.src;
    if (next) new Image().src = asset(next);
  }, [index, steps]);

  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="step"]');
    const list = listRef.current;
    if (!current || !list || list.scrollHeight <= list.clientHeight) return;
    list.scrollTo({ top: current.offsetTop - list.clientHeight / 2 + current.clientHeight / 2, behavior: 'smooth' });
  }, [index]);

  const onKeyDown = (event) => {
    if (event.target.closest('[role="tablist"]')) return;
    if (event.key === 'ArrowRight') move(1);
    else if (event.key === 'ArrowLeft') move(-1);
    else if (event.key === 'Home') setIndex(0);
    else if (event.key === 'End') setIndex(last);
    else return;
    event.preventDefault();
    setPlaying(false);
  };

  const toggle = () => {
    if (!playing && index >= last) setIndex(0);
    setPlaying((value) => !value);
  };

  if (!step) return null;

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] lg:items-start" onKeyDown={onKeyDown}>
      <div>
        <Media
          key={step.media?.src}
          media={{ frame: 'plain', ...step.media }}
          priority={index === 0}
          className="motion-safe:animate-step-in"
        />
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-soft" aria-hidden="true">
          <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${((index + 1) / steps.length) * 100}%` }} />
        </div>
      </div>

      <div className="flex flex-col gap-6">
        <div aria-live={playing ? 'off' : 'polite'} aria-atomic="true">
          <p className="font-mono text-sm text-muted">{t('walkthrough.position', { n: index + 1, total: steps.length })}</p>
          <h3 className="mt-2 font-display text-2xl font-semibold leading-tight text-fg">
            <Rich text={step.title} />
          </h3>
          {step.text ? (
            <p className="mt-3 leading-relaxed text-muted">
              <Rich text={step.text} />
            </p>
          ) : null}
        </div>

        <div className="flex items-center gap-3">
          <button type="button" className={control} onClick={() => { setPlaying(false); move(-1); }} disabled={index === 0} aria-label={t('walkthrough.prev')}>
            <ChevronLeft size={20} aria-hidden="true" />
          </button>
          <button
            type="button"
            className={`${control} w-auto gap-2 px-5 font-display text-sm font-semibold`}
            onClick={toggle}
            aria-pressed={playing}
          >
            {playing ? <Pause size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
            {playing ? t('walkthrough.pause') : t('walkthrough.play')}
          </button>
          <button type="button" className={control} onClick={() => { setPlaying(false); move(1); }} disabled={index === last} aria-label={t('walkthrough.next')}>
            <ChevronRight size={20} aria-hidden="true" />
          </button>
        </div>

        <ol ref={listRef} id={`${baseId}-list`} className="relative grid max-h-[340px] gap-1 overflow-y-auto pr-1" aria-label={t('walkthrough.steps')}>
          {steps.map((item, position) => (
            <li key={item.title}>
              <button
                type="button"
                aria-current={position === index ? 'step' : undefined}
                onClick={() => { setPlaying(false); setIndex(position); }}
                className={`flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left text-[15px] transition ${focusRing} ${
                  position === index ? 'bg-soft font-semibold text-fg' : 'text-muted hover:bg-soft/60 hover:text-fg'
                }`}
              >
                <span
                  className={`mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-xs ${
                    position === index ? 'bg-accent text-on-accent' : 'border border-line'
                  }`}
                  aria-hidden="true"
                >
                  {position + 1}
                </span>
                <Rich text={item.title} />
              </button>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export function Walkthrough({ section }) {
  const baseId = useId();
  const [view, setView] = useState('steps');
  const hasVideo = Boolean(section.video?.src);

  return (
    <Section section={section}>
      <SectionHeader section={section} />
      <Reveal className="mt-10 lg:mt-12">
        <Tabs baseId={baseId} view={view} setView={setView} hasVideo={hasVideo} />
        <div
          id={`${baseId}-panel-steps`}
          role={hasVideo ? 'tabpanel' : undefined}
          aria-labelledby={hasVideo ? `${baseId}-tab-steps` : undefined}
          hidden={view !== 'steps'}
          className={hasVideo ? 'mt-8' : ''}
        >
          {view === 'steps' ? <Steps baseId={baseId} section={section} /> : null}
        </div>
        {hasVideo ? (
          <div id={`${baseId}-panel-video`} role="tabpanel" aria-labelledby={`${baseId}-tab-video`} hidden={view !== 'video'} className="mt-8">
            {view === 'video' ? <Media media={{ type: 'video', frame: 'plain', ...section.video }} className="mx-auto max-w-[1100px]" /> : null}
          </div>
        ) : null}
        {section.caption ? (
          <p className="mt-6 max-w-[760px] text-sm leading-relaxed text-muted">
            <Rich text={section.caption} />
          </p>
        ) : null}
      </Reveal>
    </Section>
  );
}
