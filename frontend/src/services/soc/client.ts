/**
 * SOC API client — base fetcher with auth, timeout, retry, and error normalization.
 *
 * Reuses the same JWT Bearer token as the main API client (see api.ts).
 */

import { getToken } from '../api'
import type { SocError } from './contracts'

// ── Custom error class ──

class SocApiError extends Error {
  status: number
  code: string
  retryAfter?: number

  constructor(status: number, code: string, message: string, retryAfter?: number) {
    super(message)
    this.name = 'SocApiError'
    this.status = status
    this.code = code
    this.retryAfter = retryAfter
  }
}

// ── Error normalization ──

function normalizeError(err: unknown, endpoint: string): SocError {
  if (err instanceof SocApiError) {
    return {
      code: err.code,
      message: err.message,
    }
  }

  if (err instanceof TypeError || (err instanceof Error && err.message === 'Failed to fetch')) {
    return {
      code: 'NETWORK_ERROR',
      message: `Network error reaching ${endpoint}. Check your connection.`,
    }
  }

  if (err instanceof DOMException && err.name === 'AbortError') {
    return {
      code: 'TIMEOUT',
      message: `Request to ${endpoint} timed out.`,
    }
  }

  const msg = err instanceof Error ? err.message : String(err)
  return {
    code: 'UNKNOWN_ERROR',
    message: msg,
  }
}

// ── Sleep helper ──

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ── Base fetcher ──

const RENDER_FRONTEND_HOST = 'beconnect-frontend.onrender.com'
const RENDER_SOC_BACKEND_BASE = 'https://beexpand-fedeto-crm-email.onrender.com/api/v1'

function resolveSocApiBase(): string {
  const envBase = import.meta.env.VITE_SOC_API_URL?.trim()
  if (envBase) return envBase

  if (typeof window !== 'undefined' && window.location.hostname === RENDER_FRONTEND_HOST) {
    return RENDER_SOC_BACKEND_BASE
  }

  return '/api/v1'
}

const SOC_API_BASE = resolveSocApiBase()

async function socFetch<T>(
  endpoint: string,
  options?: RequestInit & { timeout?: number },
): Promise<T> {
  const timeout = options?.timeout ?? 30_000
  const maxRetries = 2

  // Separate our custom properties from native RequestInit
  const { timeout: _timeout, ...fetchOptions } = options ?? {}

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string> | undefined),
  }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const res = await fetch(`${SOC_API_BASE}${endpoint}`, {
        ...fetchOptions,
        headers,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const code = body.code || `HTTP_${res.status}`
        const message = body.message || body.detail || res.statusText || `HTTP ${res.status}`
        const retryAfter = res.headers.get('Retry-After')
          ? parseInt(res.headers.get('Retry-After')!, 10)
          : undefined

        throw new SocApiError(res.status, code, message, retryAfter)
      }

      // 204 No Content
      if (res.status === 204) return undefined as T

      return (await res.json()) as T
    } catch (err) {
      clearTimeout(timeoutId)

      // Only retry on 5xx (server errors)
      const isServerError =
        err instanceof SocApiError && err.status >= 500 && err.status < 600

      if (!isServerError || attempt === maxRetries) {
        // Last attempt or non-retryable — normalize and throw
        throw err instanceof SocApiError
          ? err
          : new SocApiError(0, normalizeError(err, endpoint).code, normalizeError(err, endpoint).message)
      }

      // Wait with exponential backoff: 1s, 2s
      const wait = Math.pow(2, attempt) * 1000
      await sleep(wait)
    }
  }

  // Exhausted retries — normalize and throw
  // This path is only hit after all 3 attempts (0,1,2) failed with 5xx
  const socErr = new SocApiError(0, 'MAX_RETRIES', `Request to ${endpoint} failed after ${maxRetries + 1} attempts.`)
  throw socErr
}

export { socFetch, SocApiError }
