import { fetchAirStudy } from '../../api/airStudy'
import { useApiResource } from '../../api/useApiResource'
import { AirScreen } from './AirScreen'
import { ErrorView, LoadingView } from './StateViews'

export function AirPage() {
  const { state, retry } = useApiResource(fetchAirStudy)
  if (state.status === 'loading') return <LoadingView />
  if (state.status === 'error') return <ErrorView error={state.error} onRetry={retry} />
  return <AirScreen bundle={state.data} />
}
