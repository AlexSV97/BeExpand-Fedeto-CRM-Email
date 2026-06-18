import { useEffect } from 'react'
import { create } from 'zustand'
import { SURFACE_IDS, type SurfaceId, type SurfaceStatus } from './contracts'
import { surfaceRegistry } from './surfaceRegistry'

// ── Store shape ──

interface SocShellState {
  activeSurfaceId: SurfaceId
  surfaceStatusMap: Record<SurfaceId, SurfaceStatus>
  dataSource: Record<SurfaceId, 'backend' | 'mock' | 'error'>
  historyStack: SurfaceId[]
  featureEnabled: boolean
}

interface SocShellActions {
  navigate: (id: SurfaceId) => void
  goBack: () => void
  setSurfaceStatus: (id: SurfaceId, status: SurfaceStatus) => void
  setDataSource: (id: SurfaceId, source: 'backend' | 'mock' | 'error') => void
  toggleFeature: () => void
  reset: () => void
}

type SocShellStore = SocShellState & SocShellActions

// ── Initial state ──

const allSurfaceIds = surfaceRegistry.getAll().map((s) => s.id)
const surfaceIdSet = new Set<SurfaceId>(allSurfaceIds)

const initialSurfaceStatusMap = Object.fromEntries(
  allSurfaceIds.map((id) => [id, 'loading' as SurfaceStatus]),
) as Record<SurfaceId, SurfaceStatus>

const initialDataSource = Object.fromEntries(
  allSurfaceIds.map((id) => [id, 'mock' as const]),
) as Record<SurfaceId, 'backend' | 'mock' | 'error'>

const initialState: SocShellState = {
  activeSurfaceId: SURFACE_IDS.COMMAND_CENTER,
  surfaceStatusMap: initialSurfaceStatusMap,
  dataSource: initialDataSource,
  historyStack: [],
  featureEnabled: false,
}

// ── Store ──

const useSocShellStore = create<SocShellStore>()((set, get) => ({
  ...initialState,

  navigate: (id: SurfaceId) => {
    const { activeSurfaceId } = get()
    if (id === activeSurfaceId) return

    // Sync with browser history so back/forward work
    window.history.pushState({ surfaceId: id }, '', '?soc=' + id)

    set((state) => ({
      historyStack: [...state.historyStack, activeSurfaceId],
      activeSurfaceId: id,
    }))
  },

  goBack: () => {
    const { historyStack } = get()
    if (historyStack.length === 0) return

    // Delegate to browser history — popstate will update the store
    window.history.back()
  },

  setSurfaceStatus: (id: SurfaceId, status: SurfaceStatus) => {
    set((state) => ({
      surfaceStatusMap: { ...state.surfaceStatusMap, [id]: status },
    }))
  },

  setDataSource: (id: SurfaceId, source: 'backend' | 'mock' | 'error') => {
    set((state) => ({
      dataSource: { ...state.dataSource, [id]: source },
    }))
  },

  toggleFeature: () => {
    set((state) => ({ featureEnabled: !state.featureEnabled }))
  },

  reset: () => {
    set(initialState)
  },
}))

// ── Browser history sync hook ──
//
// Mount this inside the SocShell component so that:
//   * Forward/back navigation restores the correct surface
//   * The `?soc=` URL param doesn't conflict with React Router path routing

function useHistorySync(): void {
  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search)
    const surfaceParam = searchParams.get('soc')
    if (surfaceParam && surfaceIdSet.has(surfaceParam as SurfaceId)) {
      const surfaceId = surfaceParam as SurfaceId
      const current = useSocShellStore.getState().activeSurfaceId
      if (surfaceId !== current) {
        useSocShellStore.setState({ activeSurfaceId: surfaceId })
      }

      window.history.replaceState({ surfaceId }, '', '?soc=' + surfaceId)
    }

    const handlePopState = (event: PopStateEvent) => {
      const surfaceId = event.state?.surfaceId as SurfaceId | undefined
      if (!surfaceId) return

      const current = useSocShellStore.getState().activeSurfaceId
      if (surfaceId === current) return

      // Update the store directly (browser already rewound history)
      useSocShellStore.setState({ activeSurfaceId: surfaceId })
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])
}

export { useSocShellStore, useHistorySync }
export type { SocShellState, SocShellActions, SocShellStore }
