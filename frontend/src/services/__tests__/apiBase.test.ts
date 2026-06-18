import { describe, expect, it, vi, afterEach } from 'vitest'
import { resolveApiBase } from '../apiBase'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('resolveApiBase', () => {
  it('uses VITE_API_URL when defined', () => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.com/api/v1')

    expect(resolveApiBase()).toBe('https://api.example.com/api/v1')
  })

  it('falls back to same-origin /api/v1 when env is missing', () => {
    vi.unstubAllEnvs()

    expect(resolveApiBase()).toBe('/api/v1')
  })
})
