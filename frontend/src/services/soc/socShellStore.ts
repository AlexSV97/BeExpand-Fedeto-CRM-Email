import { create } from 'zustand'
import { SURFACE_IDS, type SurfaceId, type SurfaceStatus } from './contracts'
import { surfaceRegistry } from './surfaceRegistry'

// ── Store shape ──

interface SocShellState {
  activeSurfaceId: SurfaceId
  surfaceStatusMap: Record<SurfaceId, SurfaceStatus>
  historyStack: SurfaceId[]
  featureEnabled: boolean
}

interface SocShellActions {
  navigate: (id: SurfaceId) => void
  goBack: () => void
  setSurfaceStatus: (id: SurfaceId, status: SurfaceStatus) => void
  toggleFeature: () => void
  reset: () => void
}

type SocShellStore = SocShellState & SocShellActions

// ── Initial state ──

const allSurfaceIds = surfaceRegistry.getAll().map((s) => s.id)

const initialSurfaceStatusMap = Object.fromEntries(
  allSurfaceIds.map((id) => [id, 'loading' as SurfaceStatus]),
) as Record<SurfaceId, SurfaceStatus>

const initialState: SocShellState = {
  activeSurfaceId: SURFACE_IDS.COMMAND_CENTER,
  surfaceStatusMap: initialSurfaceStatusMap,
  historyStack: [],
  featureEnabled: false,
}

// ── Store ──

const useSocShellStore = create<SocShellStore>()((set, get) => ({
  ...initialState,

  navigate: (id: SurfaceId) => {
    const { activeSurfaceId } = get()
    if (id === activeSurfaceId) return

    set((state) => ({
      historyStack: [...state.historyStack, activeSurfaceId],
      activeSurfaceId: id,
    }))
  },

  goBack: () => {
    const { historyStack } = get()
    if (historyStack.length === 0) return

    const previousId = historyStack[historyStack.length - 1]
    set((state) => ({
      historyStack: state.historyStack.slice(0, -1),
      activeSurfaceId: previousId,
    }))
  },

  setSurfaceStatus: (id: SurfaceId, status: SurfaceStatus) => {
    set((state) => ({
      surfaceStatusMap: { ...state.surfaceStatusMap, [id]: status },
    }))
  },

  toggleFeature: () => {
    set((state) => ({ featureEnabled: !state.featureEnabled }))
  },

  reset: () => {
    set(initialState)
  },
}))

export { useSocShellStore }
export type { SocShellState, SocShellActions, SocShellStore }
