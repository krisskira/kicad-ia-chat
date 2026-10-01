import { Media } from '../components/Media';
import { Reveal, Section, SectionHeader } from '../components/ui';

const columns = {
  2: 'sm:grid-cols-2',
  3: 'sm:grid-cols-2 lg:grid-cols-3',
  4: 'sm:grid-cols-2 lg:grid-cols-4',
};

export function Gallery({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align={section.align} />
      <div className={`mt-12 grid gap-6 lg:mt-14 ${columns[section.columns] || columns[3]}`}>
        {section.items.map((media, index) => (
          <Reveal key={media.src} delay={(index % 4) * 70}>
            <Media media={media} />
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
