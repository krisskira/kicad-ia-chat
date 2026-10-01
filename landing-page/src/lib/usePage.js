import { useMemo } from 'react';
import { useI18n } from '../i18n/useI18n';
import { localize } from '../i18n/localize';
import { landing, site } from './content';

// site y landing en el idioma activo. El español es el contenido original.
export function usePage() {
  const { locale } = useI18n();
  return useMemo(() => ({ site: localize(site, locale), landing: localize(landing, locale) }), [locale]);
}
