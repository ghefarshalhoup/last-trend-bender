import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { fetchPayload } from './series'

export type PayloadState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'success'; data: unknown }

/** Loads each element payload once, the first time a card needs it, and keeps it for the session. */
export function usePayloads(endpoints: string[]): { states: Record<string, PayloadState>; retry: (endpoint: string) => void } {
  const [states, setStates] = useState<Record<string, PayloadState>>({})
  const requested = useRef(new Set<string>())
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const load = useCallback((endpoint: string) => {
    requested.current.add(endpoint)
    setStates((s) => ({ ...s, [endpoint]: { status: 'loading' } }))
    fetchPayload(endpoint).then(
      (data) => alive.current && setStates((s) => ({ ...s, [endpoint]: { status: 'success', data } })),
      (cause: unknown) => {
        const error = cause instanceof ApiError ? cause : new ApiError('network', cause instanceof Error ? cause.message : 'Something went wrong.')
        if (alive.current) setStates((s) => ({ ...s, [endpoint]: { status: 'error', error } }))
      },
    )
  }, [])

  const key = [...new Set(endpoints)].sort().join(',')
  useEffect(() => {
    for (const endpoint of key ? key.split(',') : []) if (!requested.current.has(endpoint)) load(endpoint)
  }, [key, load])

  return { states, retry: load }
}
