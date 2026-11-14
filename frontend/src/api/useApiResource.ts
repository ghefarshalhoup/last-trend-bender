import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

export type ResourceState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError }

function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause
  return new ApiError('network', cause instanceof Error ? cause.message : 'Something went wrong.')
}

/**
 * Load a resource once on mount (or once `enabled` becomes true), abort on unmount, and expose `retry`.
 * `loader` should be stable (defined at module level or memoised).
 */
export function useApiResource<T>(loader: (signal: AbortSignal) => Promise<T>, options: { enabled?: boolean } = {}) {
  const enabled = options.enabled ?? true
  const [state, setState] = useState<ResourceState<T>>(enabled ? { status: 'loading' } : { status: 'idle' })
  const [attempt, setAttempt] = useState(0)
  const latest = useRef(loader)
  latest.current = loader

  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    setState({ status: 'loading' })
    latest.current(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: 'success', data })
      },
      (cause: unknown) => {
        if (controller.signal.aborted) return
        setState({ status: 'error', error: toApiError(cause) })
      },
    )
    return () => controller.abort()
  }, [attempt, enabled])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, retry }
}
