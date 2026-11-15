import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

// Recharts measures its container; give jsdom a real size.
Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, value: 720 })
Object.defineProperty(HTMLElement.prototype, 'clientHeight', { configurable: true, value: 360 })
Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 720 })
Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 360 })

window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
  dispatchEvent: () => false,
})) as unknown as typeof window.matchMedia
