import { Reveal, Rich, Section, SectionHeader } from '../components/ui';

export function Specs({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <div className="mt-12 grid gap-6 lg:mt-14 lg:grid-cols-2">
        {section.groups.map((group, index) => (
          <Reveal key={group.title} delay={(index % 2) * 90} className="rounded-2xl border border-line/60 bg-card p-6">
            <h3 className="font-display text-lg font-semibold text-fg">{group.title}</h3>
            <dl className="mt-4 divide-y divide-line/40">
              {group.rows.map(([label, value]) => (
                <div key={label} className="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-4 py-3 text-[15px]">
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-semibold text-fg">
                    <Rich text={value} />
                  </dd>
                </div>
              ))}
            </dl>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
