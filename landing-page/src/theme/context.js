import { createContext, useContext } from 'react';

export const ThemeContext = createContext({ theme: 'light', toggle: () => {} });

export function useTheme() {
  return useContext(ThemeContext);
}
