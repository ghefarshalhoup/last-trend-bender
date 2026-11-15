/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Dev and preview servers forward /api (JSON and chart PNGs) to FastAPI, so the
// browser only ever talks to one origin and no CORS setup is needed locally.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'
  const proxy = { '/api': { target, changeOrigin: true } }

  return {
    // GitHub Pages serves the site under /<repo>/; VITE_BASE sets that path for the static build.
    base: env.VITE_BASE || '/',
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      css: { modules: { classNameStrategy: 'non-scoped' } },
      include: ['src/**/*.test.{ts,tsx}'],
      restoreMocks: true,
    },
  }
})
