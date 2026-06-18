import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SURFACE_IDS } from '../../../services/soc/contracts'
import SocShell from '../SocShell'

const mockUseSocShell = vi.hoisted(() => vi.fn())

vi.mock('../../../services/soc/SocShellProvider', () => ({
  useSocShell: mockUseSocShell,
}))

vi.mock('../../../services/soc/socShellStore', () => ({
  useHistorySync: () => undefined,
}))

vi.mock('../../../services/soc/surfaceRegistry', () => ({
  surfaceRegistry: {
    getAll: () => [
      { id: SURFACE_IDS.COMMAND_CENTER, label: 'command.center', icon: null },
    ],
    get: () => ({ component: () => <div>Surface content</div> }),
  },
}))

vi.mock('./index', () => ({
  SocLoadingState: () => <div>Loading</div>,
}))

describe('SocShell connection badge', () => {
  it('shows Live badge for backend data', () => {
    mockUseSocShell.mockReturnValue({
      activeSurfaceId: SURFACE_IDS.COMMAND_CENTER,
      navigate: vi.fn(),
      featureEnabled: true,
      dataSource: { [SURFACE_IDS.COMMAND_CENTER]: 'backend' },
    })

    render(<SocShell />)

    expect(screen.getByText('Live')).toBeTruthy()
    expect(screen.getByText('Aiuken SOC')).toBeTruthy()
  })

  it('shows Demo badge for mock data', () => {
    mockUseSocShell.mockReturnValue({
      activeSurfaceId: SURFACE_IDS.COMMAND_CENTER,
      navigate: vi.fn(),
      featureEnabled: true,
      dataSource: { [SURFACE_IDS.COMMAND_CENTER]: 'mock' },
    })

    render(<SocShell />)

    expect(screen.getByText('Demo')).toBeTruthy()
  })

  it('shows Degraded badge for error data', () => {
    mockUseSocShell.mockReturnValue({
      activeSurfaceId: SURFACE_IDS.COMMAND_CENTER,
      navigate: vi.fn(),
      featureEnabled: true,
      dataSource: { [SURFACE_IDS.COMMAND_CENTER]: 'error' },
    })

    render(<SocShell />)

    expect(screen.getByText('Degraded')).toBeTruthy()
  })
})
