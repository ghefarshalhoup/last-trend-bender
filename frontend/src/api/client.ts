/**
 * Small typed API client.
 *
 * Base URL: `VITE_API_BASE_URL` when set (production build served from a
 * different origin than FastAPI), otherwise same-origin relative URLs. In
 * development Vite proxies `/api` to the backend, see vite.config.ts.
 */

export type ApiErrorKind =
  /** The request never reached the server (offline, refused, CORS). */
  | 'network'
  /** The server answered with a non-2xx status. */
  | 'http'
  /** The body was not valid JSON. */
  | 'parse'
  /** The JSON parsed but does not match the contract this app reads. */
  | 'schema'
  /** The catalog says the requested data is not available. */
  | 'unavailable'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status?: number
  readonly code?: string
  readonly details?: unknown

  constructor(
    kind: ApiErrorKind,
    message: string,
    extra: { status?: number; code?: string; details?: unknown } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = extra.status
    this.code = extra.code
    this.details = extra.details
  }

  /** Whether trying again can plausibly help. */
  get retryable(): boolean {
    if (this.kind === 'network') return true
    if (this.kind === 'http') return this.status === undefined || this.status >= 500
    return this.kind === 'unavailable'
  }
}

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
export const API_BASE = rawBase.replace(/\/+$/, '')

/** Turn a server-relative path such as `/api/cases` into a request URL. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

interface BackendErrorBody {
  error?: { code?: string; message?: string; details?: unknown }
}

export async function getJson<T>(path: string, init: { signal?: AbortSignal } = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      signal: init.signal,
      headers: { Accept: 'application/json' },
    })
  } catch (cause) {
    if (init.signal?.aborted) throw cause
    throw new ApiError('network', 'The server could not be reached.', { details: String(cause) })
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    if (response.ok) throw new ApiError('parse', 'The server sent a response that is not valid JSON.', { status: response.status })
    body = undefined
  }

  if (!response.ok) {
    const backend = (body as BackendErrorBody | undefined)?.error
    throw new ApiError('http', backend?.message ?? `The server answered ${response.status}.`, {
      status: response.status,
      code: backend?.code,
      details: backend?.details,
    })
  }
  return body as T
}
