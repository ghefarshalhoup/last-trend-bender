import { useEffect, useState } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { AtlasPage } from './features/atlas/AtlasPage'
import { ExplorerPage } from './features/explorer/AirExplorer'

const isAtlasRoute = () => window.location.hash.replace(/\/+$/, '') === '#/atlas'

/** `#/atlas` opens the illustrated-atlas preview; every other address keeps the tile-map explorer. */
export function App() {
  const [atlas, setAtlas] = useState(isAtlasRoute)
  useEffect(() => {
    const onChange = () => setAtlas(isAtlasRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return <ErrorBoundary>{atlas ? <AtlasPage /> : <ExplorerPage />}</ErrorBoundary>
}
