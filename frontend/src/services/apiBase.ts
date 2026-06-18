/**
 * Shared API base resolver for frontend clients.
 *
 * Prefer an explicit VITE_API_URL when present; otherwise use the same-origin
 * /api/v1 proxy path provided by the frontend deployment.
 */

function resolveApiBase(): string {
  const envBase = import.meta.env.VITE_API_URL?.trim()
  if (envBase) return envBase

  return '/api/v1'
}

export { resolveApiBase }
