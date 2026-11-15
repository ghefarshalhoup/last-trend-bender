import { ApiError } from '../../api/client'
import styles from './StateViews.module.css'

export function LoadingView() {
  return (
    <div className={styles.frame} role="status" aria-live="polite" aria-busy="true">
      <p className={styles.kicker}>Ukraine / Air — NO₂</p>
      <h1 className={styles.title}>Was NO₂ different above Kyiv in 2022?</h1>
      <p className={styles.body}>Loading the Kyiv study from the server…</p>
      <div className={styles.skeleton} aria-hidden="true">
        <span /><span /><span />
      </div>
    </div>
  )
}

const HINTS: Record<string, string> = {
  network: 'Check that the backend is running (uvicorn backend.main:app --port 8000) and that this page can reach /api.',
  http: 'The server answered, but with an error.',
  parse: 'The server sent something that is not JSON. A proxy or a wrong API address is the usual cause.',
  schema: 'The response does not match the contract this page reads. The backend and frontend may be out of sync.',
  unavailable: 'The case catalog lists this data as not ready. Generate the result artifact, then try again.',
}

export function ErrorView({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className={styles.frame} role="alert">
      <p className={styles.kicker}>Ukraine / Air — NO₂</p>
      <h1 className={styles.title}>The Kyiv study did not load</h1>
      <p className={styles.body}>{error.message}</p>
      <p className={styles.hint}>{HINTS[error.kind]}</p>
      {error.code || error.status ? (
        <p className={styles.meta}>
          {error.status ? `HTTP ${error.status}` : null}
          {error.status && error.code ? ' · ' : null}
          {error.code ?? null}
        </p>
      ) : null}
      <button type="button" className={styles.retry} onClick={onRetry}>
        Try again
      </button>
    </div>
  )
}
