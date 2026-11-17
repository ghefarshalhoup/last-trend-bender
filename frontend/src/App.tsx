import { lazy, Suspense, useEffect, useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AtlasPage } from './features/atlas/AtlasPage'
import { ExplorerPage } from './features/explorer/AirExplorer'

/** The Earth view brings its own map engine, so it loads only when its address is opened. */
const EarthPage = lazy(() => import('./features/earth/EarthPage'))

type Route = 'atlas' | 'earth' | 'explorer'

const currentRoute = (): Route => {
  const hash = window.location.hash.replace(/\/+$/, '')
  return hash === '#/atlas' ? 'atlas' : hash === '#/earth' ? 'earth' : 'explorer'
}

/** `#/atlas` opens the illustrated atlas, `#/earth` the explorable Earth; every other address keeps the tile-map explorer. */
export function App() {
  const [route, setRoute] = useState(currentRoute)
  useEffect(() => {
    const onChange = () => setRoute(currentRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return (
    <ErrorBoundary>
      {route === 'earth' ? (
        <Suspense fallback={<div style={{ position: 'fixed', inset: 0, background: '#020308' }} role="status" aria-label="Loading the Earth" />}>
          <EarthPage />
        </Suspense>
      ) : route === 'atlas' ? (
        <AtlasPage />
      ) : (
        <ExplorerPage />
      )}
    </ErrorBoundary>
  )
}
