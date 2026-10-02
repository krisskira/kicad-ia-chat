import { Media } from '../components/Media';
import { Actions, Reveal, Rich, Section, SectionHeader } from '../components/ui';

function Beats({ beats }) {
  if (!beats?.length) return null;
  return (
    <dl className="mt-5 grid gap-4">
      {beats.map((beat) => (
        <div key={beat.label}>
          <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{beat.label}</dt>
          <dd className="mt-1 leading-relaxed text-muted">
            <Rich text={beat.text} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Tags({ tags }) {
  if (!tags?.length) return null;
  return (
    <ul className="mt-6 flex flex-wrap gap-2">
      {tags.map((tag) => (
        <li key={tag} className="rounded-full border border-line/70 px-3 py-1 font-mono text-xs text-muted">
          {tag}
        </li>
      ))}
    </ul>
  );
}

function ProjectCard({ item, index }) {
  const featured = item.featured && item.media;
  return (
    <Reveal
      as="li"
      id={item.id}
      delay={(index % 2) * 90}
      className={`flex flex-col overflow-hidden rounded-2xl border border-line/60 bg-card transition hover:border-accent/60 hover:shadow-card ${
        featured ? 'lg:col-span-2 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]' : ''
      }`}
    >
      {item.media ? (
        <div className={`border-b border-line/60 bg-soft p-4 sm:p-5 ${featured ? 'lg:border-b-0 lg:border-r lg:p-6' : ''}`}>
          <Media media={{ ...item.media, frame: 'plain' }} className={featured ? 'lg:flex lg:h-full lg:flex-col lg:justify-center' : ''} />
        </div>
      ) : null}
      <div className="flex flex-1 flex-col p-6 lg:p-8">
        {item.meta ? <p className="font-mono text-xs font-semibold uppercase tracking-wider text-muted">{item.meta}</p> : null}
        <h3 className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 font-display text-2xl font-semibold leading-snug text-fg">
          <Rich text={item.title} />
          {item.badge ? (
            <span className="rounded-full border border-accent/40 px-2 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-accent">
              {item.badge}
            </span>
          ) : null}
        </h3>
        {item.summary ? (
          <p className="mt-3 text-[17px] leading-relaxed text-fg/90">
            <Rich text={item.summary} />
          </p>
        ) : null}
        <Beats beats={item.beats} />
        <Tags tags={item.tags} />
        {item.actions?.length ? (
          <div className="mt-auto pt-6">
            <Actions actions={item.actions.map((action) => ({ variant: 'link', ...action }))} className="gap-6" />
          </div>
        ) : null}
      </div>
    </Reveal>
  );
}

export function Projects({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <ul className="mt-12 grid gap-6 lg:mt-16 lg:grid-cols-2">
        {section.items.map((item, index) => (
          <ProjectCard key={item.title} item={item} index={index} />
        ))}
      </ul>
      <Actions actions={section.actions} className="mt-12" />
    </Section>
  );
}
