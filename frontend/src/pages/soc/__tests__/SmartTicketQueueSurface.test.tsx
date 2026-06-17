/**
 * Tests for SmartTicketQueueSurface — specifically the operating mode badge.
 *
 * The component uses useSocResource for data fetching and useSocShell for
 * navigation. We mock both to control the view data.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import SmartTicketQueueSurface from '../SmartTicketQueueSurface'
import type { TicketQueueView } from '../../../services/soc/normalize/ticketQueue'

// ── Mock useSocShell ────────────────────────────────────────────────────────

const mockNavigate = vi.fn()

vi.mock('../../../services/soc/SocShellProvider', () => ({
  useSocShell: () => ({
    navigate: mockNavigate,
  }),
}))

// ── Mock useSocResource ─────────────────────────────────────────────────────

const mockUseSocResource = vi.hoisted(() => vi.fn())

vi.mock('../../../services/soc/useSocResource', () => ({
  useSocResource: mockUseSocResource,
}))

// ── Default mock data helper ────────────────────────────────────────────────

function createMockView(overrides: Partial<TicketQueueView> = {}): TicketQueueView {
  return {
    tickets: [
      {
        id: 'TKT-001',
        subject: 'Test ticket',
        status: 'open',
        priority: 'high',
        createdAt: '2026-06-17T08:00:00Z',
        updatedAt: '2026-06-17T09:00:00Z',
      },
    ],
    total: 1,
    page: 1,
    filters: { status: ['open'], priority: ['high'], assignee: [] },
    operatingMode: 'demo',
    ...overrides,
  }
}

function mockSocResourceResponse(view: TicketQueueView) {
  mockUseSocResource.mockReturnValue({
    data: view,
    loading: false,
    error: null,
    source: 'mock',
    refresh: vi.fn(),
  })
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe('SmartTicketQueueSurface — operating mode badge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Demo badge when operatingMode is "demo"', () => {
    mockSocResourceResponse(createMockView({ operatingMode: 'demo' }))
    render(<SmartTicketQueueSurface />)
    expect(screen.getByText('Demo')).toBeTruthy()
  })

  it('renders Live badge when operatingMode is "live"', () => {
    mockSocResourceResponse(createMockView({ operatingMode: 'live' }))
    render(<SmartTicketQueueSurface />)
    expect(screen.getByText('Live')).toBeTruthy()
  })

  it('renders Degraded badge when operatingMode is "degraded"', () => {
    mockSocResourceResponse(createMockView({ operatingMode: 'degraded' }))
    render(<SmartTicketQueueSurface />)
    expect(screen.getByText('Degraded')).toBeTruthy()
  })

  it('renders badge with correct text for each operating mode', () => {
    mockSocResourceResponse(createMockView({ operatingMode: 'live' }))
    const { rerender } = render(<SmartTicketQueueSurface />)
    expect(screen.getByText('Live')).toBeTruthy()

    mockSocResourceResponse(createMockView({ operatingMode: 'demo' }))
    rerender(<SmartTicketQueueSurface />)
    expect(screen.getByText('Demo')).toBeTruthy()

    mockSocResourceResponse(createMockView({ operatingMode: 'degraded' }))
    rerender(<SmartTicketQueueSurface />)
    expect(screen.getByText('Degraded')).toBeTruthy()
  })
})
