import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

export type ResourceState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError }

function toApiError(cause: unknown): ApiError {
  if (cause instanceof ApiError) return cause
  return new ApiError('network', cause instanceof Error ? cause.message : 'Something went wrong.')
}

/**
 * Load a resource once on mount, abort on unmount, and expose `retry`.
 * `loader` should be stable (defined at module level or memoised).
 */
export function useApiResource<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const latest = useRef(loader)
  latest.current = loader

  useEffect(() => {
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
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, retry }
}
