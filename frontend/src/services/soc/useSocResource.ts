/**
 * useSocResource — Shared hook for fetching SOC resources with mock fallback.
 *
 * All 9 SOC surfaces use this hook instead of repeating fetch + error +
 * loading + mock logic. The hook centralises the dataSource tracking so
 * each surface can show a "Demo mode" indicator when data comes from mock.
 *
 * ── Behaviour ─────────────────────────────────────────────────────────
 * 1. On mount (and on refresh) the hook calls socFetch(endpoint).
 * 2. If the fetch succeeds the raw response is passed through the
 *    normalizer and returned as typed data + source 'backend'.
 * 3. If the fetch fails or throws, the hook falls back to mockData
 *    and sets source to 'mock'. The error message is still returned so
 *    the surface can choose to render SocErrorState or stay silent.
 * 4. On successful fetch, the error is cleared.
 * 5. surfaceId is optional — when provided the hook also updates
 *    useSocShellStore's dataSource for the corresponding surface so the
 *    shell shows the demo badge.
 *
 * ── Signature ─────────────────────────────────────────────────────────
 *   useSocResource<T>(
 *     endpoint: string,
 *     normalizer: (raw: unknown) => T,
 *     mockData: T,
 *     surfaceId?: SurfaceId,
 *   ): SocResourceResult<T>
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { socFetch } from './client'
import { useSocShellStore } from './socShellStore'
import type { SurfaceId } from './contracts'

// ── Public types ───────────────────────────────────────────────────────

export interface SocResourceResult<T> {
  /** The typed view data — either from the backend or mock fallback. */
  data: T
  /** True while the fetch request is outstanding. */
  loading: boolean
  /** Human-readable error message when fetch fails; null otherwise. */
  error: string | null
  /** Indicates the source of the data, so the surface can react. */
  source: 'backend' | 'mock' | 'error'
  /** Re-fetch the endpoint (clears error and loading state). */
  refresh: () => void
}

// ── Hook ───────────────────────────────────────────────────────────────

/**
 * Optional callback invoked with the raw fetch response on success.
 * Surfaces use this to extract supplementary data (e.g. SLA risk items,
 * rich articles, chart data) that live alongside the normalised view.
 */
export type OnSocFetchSuccess = (raw: unknown) => void

export function useSocResource<T>(
  endpoint: string,
  normalizer: (raw: Record<string, unknown>) => T,
  mockData: T,
  surfaceId?: SurfaceId,
  onSuccess?: OnSocFetchSuccess,
): SocResourceResult<T> {
  const [data, setData] = useState<T>(mockData)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<'backend' | 'mock' | 'error'>('mock')

  // Track if the component is still mounted to avoid state updates after
  // unmount (React 18 Strict Mode safety).
  const mountedRef = useRef(true)

  const setDataSource = useSocShellStore((s) => s.setDataSource)

  const fetchResource = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const raw = await socFetch(endpoint)
      const normalized = normalizer(raw as Record<string, unknown>)

      if (mountedRef.current) {
        setData(normalized)
        setSource('backend')
        setLoading(false)
        setError(null)
        if (surfaceId) {
          setDataSource(surfaceId, 'backend')
        }
        onSuccess?.(raw)
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        // Keep the previous mock data — do not overwrite it.
        setSource('mock')
        setLoading(false)

        const msg =
          err instanceof Error
            ? err.message
            : 'Unknown error fetching data'

        setError(msg)

        if (surfaceId) {
          setDataSource(surfaceId, 'mock')
        }
      }
    }
  }, [endpoint, normalizer, surfaceId, setDataSource, onSuccess])

  useEffect(() => {
    fetchResource()
  }, [fetchResource])

  // Cleanup flag on unmount.
  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refresh = useCallback(() => {
    fetchResource()
  }, [fetchResource])

  return { data, loading, error, source, refresh }
}
