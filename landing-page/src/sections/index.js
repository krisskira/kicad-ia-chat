import { Code } from './Code';
import { Cta } from './Cta';
import { Faq } from './Faq';
import { Features } from './Features';
import { Gallery } from './Gallery';
import { Hero } from './Hero';
import { Journey } from './Journey';
import { Projects } from './Projects';
import { Quotes } from './Quotes';
import { Showcase } from './Showcase';
import { Specs } from './Specs';
import { Split } from './Split';
import { Stats } from './Stats';
import { Steps } from './Steps';
import { Video } from './Video';

/** "type" en content/landing.json → componente. */
export const sections = {
  hero: Hero,
  features: Features,
  split: Split,
  showcase: Showcase,
  video: Video,
  steps: Steps,
  stats: Stats,
  specs: Specs,
  code: Code,
  faq: Faq,
  gallery: Gallery,
  journey: Journey,
  projects: Projects,
  quotes: Quotes,
  cta: Cta,
};
