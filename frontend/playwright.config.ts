import { defineConfig, devices } from '@playwright/test'

const FRONTEND_PORT = 5173
const BACKEND_PORT = 8000

// The smoke test runs against the REAL FastAPI backend (started from the repo root)
// through the Vite dev proxy, exactly like local development.
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    channel: 'chrome',
  },
  webServer: [
    {
      command: `${process.platform === 'win32' ? 'python' : 'python3'} -m uvicorn backend.main:app --port ${BACKEND_PORT}`,
      cwd: '..',
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
