/**
 * Tests for useSocResource — the shared SOC data-fetching hook.
 *
 * The hook uses socFetch from the client module, which we mock to
 * control success / failure scenarios without real HTTP calls.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useSocResource } from '../useSocResource'
import { SURFACE_IDS } from '../contracts'
import { useSocShellStore } from '../socShellStore'

// ---------------------------------------------------------------------------
// Mock the client module
// Use vi.hoisted to create the mock function before hoisting takes effect
// ---------------------------------------------------------------------------

const mockSocFetch = vi.hoisted(() => vi.fn())

vi.mock('../client', () => ({
  socFetch: mockSocFetch,
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface TestView {
  id: string
  name: string
}

const MOCK_DATA: TestView = { id: 'mock-1', name: 'Mock Fallback' }

const VALID_RESPONSE: Record<string, unknown> = {
  id: 'real-1',
  name: 'Backend Data',
}

const normalizer = (raw: Record<string, unknown>): TestView => ({
  id: raw.id as string,
  name: raw.name as string,
})

const ENDPOINT = '/soc/test-endpoint'

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useSocResource', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Reset useSocShellStore before each test so dataSource state is clean
    useSocShellStore.getState().reset()
  })

  it('returns mock data initially (loading = true)', () => {
    // Don't resolve the promise yet so we see the loading state
    mockSocFetch.mockImplementation(() => new Promise(() => {}))

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    expect(result.current.data).toEqual(MOCK_DATA)
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBeNull()
    expect(result.current.source).toBe('mock')
  })

  it('calls socFetch with the correct endpoint', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)

    renderHook(() => useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA))

    await waitFor(() => {
      expect(mockSocFetch).toHaveBeenCalledWith(ENDPOINT)
    })
  })

  it('updates data when fetch succeeds', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual({ id: 'real-1', name: 'Backend Data' })
    expect(result.current.source).toBe('backend')
    expect(result.current.error).toBeNull()
  })

  it('falls back to mock data when fetch fails', async () => {
    mockSocFetch.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Should still have the mock data (it was the initial value)
    expect(result.current.data).toEqual(MOCK_DATA)
    expect(result.current.source).toBe('mock')
    expect(result.current.error).toBe('Network error')
  })

  it('sets loading = false after fetch completes', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    // Starts loading
    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })

  it('sets loading = false when fetch fails too', async () => {
    mockSocFetch.mockRejectedValue(new Error('Failure'))

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })

  it('updates dataSource in the shell store on success when surfaceId is provided', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)

    renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA, SURFACE_IDS.COMMAND_CENTER),
    )

    await waitFor(() => {
      const state = useSocShellStore.getState()
      expect(state.dataSource[SURFACE_IDS.COMMAND_CENTER]).toBe('backend')
    })
  })

  it('does not update dataSource when surfaceId is omitted', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)

    renderHook(() => useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA))

    await waitFor(() => {
      expect(mockSocFetch).toHaveBeenCalled()
    })

    const state = useSocShellStore.getState()
    // Should still be 'mock' because we didn't pass a surfaceId
    expect(state.dataSource[SURFACE_IDS.COMMAND_CENTER]).toBe('mock')
  })

  it('calls onSuccess callback with raw data when fetch succeeds', async () => {
    mockSocFetch.mockResolvedValue(VALID_RESPONSE)
    const onSuccess = vi.fn()

    renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA, undefined, onSuccess),
    )

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(VALID_RESPONSE)
    })
  })

  it('refresh() refetches data and clears error', async () => {
    // First call fails
    mockSocFetch.mockRejectedValueOnce(new Error('First failure'))

    const { result } = renderHook(() =>
      useSocResource<TestView>(ENDPOINT, normalizer, MOCK_DATA),
    )

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('First failure')

    // Second call succeeds
    mockSocFetch.mockResolvedValueOnce(VALID_RESPONSE)

    act(() => {
      result.current.refresh()
    })

    // Should be loading again
    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual({ id: 'real-1', name: 'Backend Data' })
    expect(result.current.error).toBeNull()
    expect(result.current.source).toBe('backend')
  })
})
