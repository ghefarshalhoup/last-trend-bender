import { fetchCatalog } from '../../api/airStudy'
import { useApiResource } from '../../api/useApiResource'
import { ErrorView, LoadingView } from '../air/StateViews'
import { fetchComparisonWeather, fetchNo2Regional, fetchVariableCatalog, NO_COMPARISON_WEATHER, NO_REGIONAL_NO2 } from '../investigate/catalog'
import { InvestigationAtlas } from '../investigate/InvestigationAtlas'
import { fetchTrends, type TrendsPayload } from '../investigate/series'

/** Illustrated atlas (#/atlas): choose a place and period, then open variables as cards over the map. */
export function AtlasPage() {
  const { state, retry } = useApiResource(loadAtlas)
  if (state.status === 'idle' || state.status === 'loading') return <LoadingView />
  if (state.status === 'error') return <ErrorView error={state.error} onRetry={retry} />
  return <InvestigationAtlas {...state.data} />
}

const NO_TRENDS: TrendsPayload = { status: 'not_available', results: [] }

/** Catalog, variables, trend results and regional NO₂ in parallel. Missing trend results are not an error: cards then say "not assessed". */
async function loadAtlas(signal: AbortSignal) {
  const [cases, catalog, trends, no2Regional, comparisonWeather] = await Promise.all([
    fetchCatalog(signal),
    fetchVariableCatalog(signal),
    fetchTrends(signal).catch(() => NO_TRENDS),
    fetchNo2Regional(signal).catch(() => NO_REGIONAL_NO2),
    fetchComparisonWeather(signal).catch(() => NO_COMPARISON_WEATHER),
  ])
  return { cases, catalog, trends, no2Regional, comparisonWeather }
}
