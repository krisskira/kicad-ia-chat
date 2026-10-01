import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { landingFiles } from './scripts/vite-plugin-landing.js';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_');
  const port = env.VITE_PORT ? Number(env.VITE_PORT) : undefined;

  return {
    plugins: [react(), tailwindcss(), landingFiles({ siteUrl: env.VITE_SITE_URL })],
    base: './',
    server: { port },
    preview: { port },
  };
});
