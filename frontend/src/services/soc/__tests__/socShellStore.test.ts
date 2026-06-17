/**
 * Tests for the SOC shell Zustand store.
 *
 * Covers: initial state, navigation, history, surface status,
 * data source tracking, feature toggle, and reset.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSocShellStore } from '../socShellStore'
import { SURFACE_IDS } from '../contracts'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Reset the store to initial state before each test.
 * We call store.getState().reset() which sets the store back to initialState.
 */
beforeEach(() => {
  useSocShellStore.getState().reset()
  vi.clearAllMocks()

  // Mock window.history.pushState / back so tests don't touch real history
  vi.spyOn(window.history, 'pushState').mockImplementation(() => {})
  vi.spyOn(window.history, 'back').mockImplementation(() => {})
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('socShellStore — initial state', () => {
  it('starts with COMMAND_CENTER as the active surface', () => {
    const state = useSocShellStore.getState()
    expect(state.activeSurfaceId).toBe(SURFACE_IDS.COMMAND_CENTER)
  })

  it('starts with all surfaces in loading status', () => {
    const state = useSocShellStore.getState()
    const surfaceIds = Object.values(SURFACE_IDS)
    for (const id of surfaceIds) {
      expect(state.surfaceStatusMap[id]).toBe('loading')
    }
  })

  it('starts with all data sources set to mock', () => {
    const state = useSocShellStore.getState()
    const surfaceIds = Object.values(SURFACE_IDS)
    for (const id of surfaceIds) {
      expect(state.dataSource[id]).toBe('mock')
    }
  })

  it('starts with an empty history stack', () => {
    const state = useSocShellStore.getState()
    expect(state.historyStack).toEqual([])
  })

  it('starts with featureEnabled = false', () => {
    const state = useSocShellStore.getState()
    expect(state.featureEnabled).toBe(false)
  })
})

describe('socShellStore — navigate', () => {
  it('updates activeSurfaceId on navigate', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.SMART_TICKET_QUEUE)

    const state = useSocShellStore.getState()
    expect(state.activeSurfaceId).toBe(SURFACE_IDS.SMART_TICKET_QUEUE)
  })

  it('pushes the previous surface onto historyStack', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.SMART_TICKET_QUEUE)

    const state = useSocShellStore.getState()
    expect(state.historyStack).toContain(SURFACE_IDS.COMMAND_CENTER)
  })

  it('does nothing when navigating to the same surface', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.COMMAND_CENTER)

    const state = useSocShellStore.getState()
    expect(state.historyStack).toEqual([])
    expect(state.activeSurfaceId).toBe(SURFACE_IDS.COMMAND_CENTER)
  })

  it('builds a stack across multiple navigations', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.SMART_TICKET_QUEUE)
    store.navigate(SURFACE_IDS.SLA_WAR_ROOM)
    store.navigate(SURFACE_IDS.KNOWLEDGE_VAULT)

    const state = useSocShellStore.getState()
    expect(state.historyStack).toEqual([
      SURFACE_IDS.COMMAND_CENTER,
      SURFACE_IDS.SMART_TICKET_QUEUE,
      SURFACE_IDS.SLA_WAR_ROOM,
    ])
    expect(state.activeSurfaceId).toBe(SURFACE_IDS.KNOWLEDGE_VAULT)
  })

  it('calls window.history.pushState with the surfaceId', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.TICKET_COPILOT)

    expect(window.history.pushState).toHaveBeenCalledWith(
      { surfaceId: SURFACE_IDS.TICKET_COPILOT },
      '',
      '?soc=' + SURFACE_IDS.TICKET_COPILOT,
    )
  })
})

describe('socShellStore — goBack', () => {
  it('restores the previous surface from historyStack', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.SMART_TICKET_QUEUE)
    store.navigate(SURFACE_IDS.SLA_WAR_ROOM)

    // Reset mock call count after navigate
    vi.mocked(window.history.back).mockClear()

    useSocShellStore.getState().goBack()
    expect(window.history.back).toHaveBeenCalled()
  })

  it('does nothing when historyStack is empty', () => {
    const store = useSocShellStore.getState()
    store.goBack()

    expect(window.history.back).not.toHaveBeenCalled()
  })
})

describe('socShellStore — setSurfaceStatus', () => {
  it('updates status for a given surface', () => {
    const store = useSocShellStore.getState()
    store.setSurfaceStatus(SURFACE_IDS.COMMAND_CENTER, 'ready')

    const state = useSocShellStore.getState()
    expect(state.surfaceStatusMap[SURFACE_IDS.COMMAND_CENTER]).toBe('ready')
  })

  it('does not affect other surfaces', () => {
    const store = useSocShellStore.getState()
    store.setSurfaceStatus(SURFACE_IDS.COMMAND_CENTER, 'ready')

    const state = useSocShellStore.getState()
    expect(state.surfaceStatusMap[SURFACE_IDS.SMART_TICKET_QUEUE]).toBe('loading')
  })

  it('accepts all valid statuses: loading, ready, error, stale', () => {
    const store = useSocShellStore.getState()
    store.setSurfaceStatus(SURFACE_IDS.COMMAND_CENTER, 'loading')
    store.setSurfaceStatus(SURFACE_IDS.SMART_TICKET_QUEUE, 'ready')
    store.setSurfaceStatus(SURFACE_IDS.SLA_WAR_ROOM, 'error')
    store.setSurfaceStatus(SURFACE_IDS.KNOWLEDGE_VAULT, 'stale')

    const state = useSocShellStore.getState()
    expect(state.surfaceStatusMap[SURFACE_IDS.COMMAND_CENTER]).toBe('loading')
    expect(state.surfaceStatusMap[SURFACE_IDS.SMART_TICKET_QUEUE]).toBe('ready')
    expect(state.surfaceStatusMap[SURFACE_IDS.SLA_WAR_ROOM]).toBe('error')
    expect(state.surfaceStatusMap[SURFACE_IDS.KNOWLEDGE_VAULT]).toBe('stale')
  })
})

describe('socShellStore — setDataSource', () => {
  it('updates data source for a given surface', () => {
    const store = useSocShellStore.getState()
    store.setDataSource(SURFACE_IDS.COMMAND_CENTER, 'backend')

    const state = useSocShellStore.getState()
    expect(state.dataSource[SURFACE_IDS.COMMAND_CENTER]).toBe('backend')
  })

  it('does not affect other surfaces', () => {
    const store = useSocShellStore.getState()
    store.setDataSource(SURFACE_IDS.COMMAND_CENTER, 'backend')

    const state = useSocShellStore.getState()
    expect(state.dataSource[SURFACE_IDS.SMART_TICKET_QUEUE]).toBe('mock')
  })

  it('accepts backend, mock, and error sources', () => {
    const store = useSocShellStore.getState()
    store.setDataSource(SURFACE_IDS.COMMAND_CENTER, 'backend')
    store.setDataSource(SURFACE_IDS.SMART_TICKET_QUEUE, 'mock')
    store.setDataSource(SURFACE_IDS.SLA_WAR_ROOM, 'error')

    const state = useSocShellStore.getState()
    expect(state.dataSource[SURFACE_IDS.COMMAND_CENTER]).toBe('backend')
    expect(state.dataSource[SURFACE_IDS.SMART_TICKET_QUEUE]).toBe('mock')
    expect(state.dataSource[SURFACE_IDS.SLA_WAR_ROOM]).toBe('error')
  })
})

describe('socShellStore — toggleFeature', () => {
  it('flips featureEnabled from false to true', () => {
    const store = useSocShellStore.getState()
    expect(store.featureEnabled).toBe(false)

    store.toggleFeature()
    expect(useSocShellStore.getState().featureEnabled).toBe(true)
  })

  it('flips featureEnabled from true to false', () => {
    useSocShellStore.getState().toggleFeature()
    expect(useSocShellStore.getState().featureEnabled).toBe(true)

    useSocShellStore.getState().toggleFeature()
    expect(useSocShellStore.getState().featureEnabled).toBe(false)
  })
})

describe('socShellStore — reset', () => {
  it('resets to initial state after mutations', () => {
    const store = useSocShellStore.getState()
    store.navigate(SURFACE_IDS.SMART_TICKET_QUEUE)
    store.setSurfaceStatus(SURFACE_IDS.COMMAND_CENTER, 'ready')
    store.setDataSource(SURFACE_IDS.COMMAND_CENTER, 'backend')
    store.toggleFeature()

    store.reset()

    const state = useSocShellStore.getState()
    expect(state.activeSurfaceId).toBe(SURFACE_IDS.COMMAND_CENTER)
    expect(state.surfaceStatusMap[SURFACE_IDS.COMMAND_CENTER]).toBe('loading')
    expect(state.dataSource[SURFACE_IDS.COMMAND_CENTER]).toBe('mock')
    expect(state.featureEnabled).toBe(false)
    expect(state.historyStack).toEqual([])
  })
})
