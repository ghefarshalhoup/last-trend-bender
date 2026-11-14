import { ErrorBoundary } from './components/ErrorBoundary'
import { ExplorerPage } from './features/explorer/AirExplorer'

export function App() {
  return (
    <ErrorBoundary>
      <ExplorerPage />
    </ErrorBoundary>
  )
}
