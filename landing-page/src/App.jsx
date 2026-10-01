import { Footer } from './components/Footer';
import { Header } from './components/Header';
import { Seo } from './components/Seo';
import { LocaleProvider } from './i18n/LocaleProvider';
import { useI18n } from './i18n/useI18n';
import { usePage } from './lib/usePage';
import { sections } from './sections';
import { ThemeProvider } from './theme/ThemeProvider';

export default function App() {
  return (
    <ThemeProvider>
      <LocaleProvider>
        <Page />
      </LocaleProvider>
    </ThemeProvider>
  );
}

function Page() {
  const { t } = useI18n();
  const { landing } = usePage();
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <Seo />
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-accent focus:px-4 focus:py-2 focus:font-display focus:text-on-accent"
      >
        {t('skip')}
      </a>
      <Header />
      <main id="contenido" className="flex-1">
        {landing.sections.map((section, index) => {
          const Component = sections[section.type];
          if (!Component) {
            if (import.meta.env.DEV) console.warn(`Sección desconocida: "${section.type}"`);
            return null;
          }
          return <Component key={section.id || `${section.type}-${index}`} section={section} />;
        })}
      </main>
      <Footer />
    </div>
  );
}
