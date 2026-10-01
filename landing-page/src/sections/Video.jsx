import { Media } from '../components/Media';
import { Reveal, Section, SectionHeader } from '../components/ui';

export function Video({ section }) {
  return (
    <Section section={section}>
      <SectionHeader section={section} align="center" />
      <Reveal className="mx-auto mt-12 max-w-[1100px] lg:mt-14">
        <Media media={{ type: 'video', frame: 'plain', ...section.video }} />
      </Reveal>
    </Section>
  );
}
