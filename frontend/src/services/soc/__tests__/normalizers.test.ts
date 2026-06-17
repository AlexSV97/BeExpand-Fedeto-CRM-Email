/**
 * Tests for all 9 SOC data normalizers.
 *
 * Each normalizer is tested with:
 * 1. Valid input → returns expected shape
 * 2. null/undefined → returns fallback defaults
 * 3. Non-object primitive → returns fallback defaults
 */

import { describe, it, expect } from 'vitest'
import { normalizeCommandCenter } from '../normalize/commandCenter'
import { normalizeTicketQueue } from '../normalize/ticketQueue'
import { normalizeTicketCopilot } from '../normalize/ticketCopilot'
import { normalizeSlaWarRoom } from '../normalize/slaWarRoom'
import { normalizeKnowledgeVault } from '../normalize/knowledgeVault'
import { normalizeAgentGovernance } from '../normalize/agentGovernance'
import { normalizeReporting } from '../normalize/reporting'
import { normalizeAudit } from '../normalize/audit'
import { normalizeConfiguration } from '../normalize/configuration'

// =========================================================================
// normalizeCommandCenter
// =========================================================================

describe('normalizeCommandCenter', () => {
  const validInput = {
    kpiCards: [
      { label: 'Active Tickets', value: 1247, trend: 'up', change: 8 },
    ],
    recentAlerts: [
      { id: 'a1', severity: 'critical', message: 'Test alert', timestamp: '2026-01-01T00:00:00Z' },
    ],
    queuePressure: 68,
    surfaceStatus: 'operational',
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeCommandCenter(validInput)
    expect(result).toHaveProperty('kpiCards')
    expect(result).toHaveProperty('recentAlerts')
    expect(result).toHaveProperty('queuePressure')
    expect(result).toHaveProperty('surfaceStatus')
    expect(result.kpiCards).toHaveLength(1)
    expect(result.recentAlerts).toHaveLength(1)
    expect(result.queuePressure).toBe(68)
    expect(result.surfaceStatus).toBe('operational')
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeCommandCenter(null as unknown as Record<string, unknown>)
    expect(result.kpiCards).toEqual([])
    expect(result.recentAlerts).toEqual([])
    expect(result.queuePressure).toBe(0)
    expect(result.surfaceStatus).toBe('error')
  })

  it('returns fallback when undefined is passed', () => {
    const result = normalizeCommandCenter(undefined as unknown as Record<string, unknown>)
    expect(result.kpiCards).toEqual([])
    expect(result.recentAlerts).toEqual([])
    expect(result.surfaceStatus).toBe('error')
  })

  it('returns fallback when a string is passed', () => {
    const result = normalizeCommandCenter('invalid' as unknown as Record<string, unknown>)
    expect(result.kpiCards).toEqual([])
    expect(result.surfaceStatus).toBe('error')
  })

  it('handles missing fields gracefully', () => {
    const result = normalizeCommandCenter({})
    expect(result.kpiCards).toEqual([])
    expect(result.recentAlerts).toEqual([])
    expect(result.queuePressure).toBe(0)
    expect(result.surfaceStatus).toBe('unknown')
  })

  it('preserves array items when present', () => {
    const result = normalizeCommandCenter({
      kpiCards: validInput.kpiCards,
    })
    expect(result.kpiCards).toHaveLength(1)
    expect(result.recentAlerts).toEqual([])
  })
})

// =========================================================================
// normalizeTicketQueue
// =========================================================================

describe('normalizeTicketQueue', () => {
  const validInput = {
    tickets: [
      { id: 'TKT-001', subject: 'Test ticket', status: 'open', priority: 'high', createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T01:00:00Z' },
    ],
    total: 1,
    page: 1,
    filters: { status: ['open'], priority: ['high'], assignee: [] },
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeTicketQueue(validInput)
    expect(result).toHaveProperty('tickets')
    expect(result).toHaveProperty('total')
    expect(result).toHaveProperty('page')
    expect(result).toHaveProperty('filters')
    expect(result.tickets).toHaveLength(1)
    expect(result.total).toBe(1)
    expect(result.page).toBe(1)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeTicketQueue(null as unknown as Record<string, unknown>)
    expect(result.tickets).toEqual([])
    expect(result.total).toBe(0)
    expect(result.page).toBe(1)
    expect(result.filters).toEqual({})
  })

  it('returns fallback when undefined is passed', () => {
    const result = normalizeTicketQueue(undefined as unknown as Record<string, unknown>)
    expect(result.tickets).toEqual([])
    expect(result.total).toBe(0)
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeTicketQueue(42 as unknown as Record<string, unknown>)
    expect(result.tickets).toEqual([])
    expect(result.total).toBe(0)
  })

  it('handles missing fields gracefully', () => {
    const result = normalizeTicketQueue({})
    expect(result.tickets).toEqual([])
    expect(result.total).toBe(0)
    expect(result.page).toBe(1)
    expect(result.filters).toEqual({})
  })

  it('handles empty ticket array', () => {
    const result = normalizeTicketQueue({ tickets: [], total: 0, page: 1, filters: {} })
    expect(result.tickets).toEqual([])
    expect(result.total).toBe(0)
  })
})

// =========================================================================
// normalizeTicketCopilot
// =========================================================================

describe('normalizeTicketCopilot', () => {
  const validInput = {
    conversation: [
      { role: 'system', content: 'Session started', timestamp: '2026-01-01T00:00:00Z' },
    ],
    suggestedActions: [
      { id: 's1', label: 'Rollback', action: 'rollback' },
    ],
    ticketContext: { ticketId: 'TKT-001', subject: 'Test', status: 'open' },
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeTicketCopilot(validInput)
    expect(result).toHaveProperty('conversation')
    expect(result).toHaveProperty('suggestedActions')
    expect(result).toHaveProperty('ticketContext')
    expect(result.conversation).toHaveLength(1)
    expect(result.suggestedActions).toHaveLength(1)
    expect(result.ticketContext.ticketId).toBe('TKT-001')
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeTicketCopilot(null as unknown as Record<string, unknown>)
    expect(result.conversation).toEqual([])
    expect(result.suggestedActions).toEqual([])
    expect(result.ticketContext).toEqual({ ticketId: '', subject: '', status: '' })
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeTicketCopilot(true as unknown as Record<string, unknown>)
    expect(result.conversation).toEqual([])
    expect(result.ticketContext.ticketId).toBe('')
  })

  it('handles missing ticketContext gracefully', () => {
    const result = normalizeTicketCopilot({ conversation: [], suggestedActions: [] })
    expect(result.ticketContext).toEqual({ ticketId: '', subject: '', status: '' })
  })

  it('preserves suggestions when provided', () => {
    const result = normalizeTicketCopilot(validInput)
    expect(result.suggestedActions[0].label).toBe('Rollback')
  })
})

// =========================================================================
// normalizeSlaWarRoom
// =========================================================================

describe('normalizeSlaWarRoom', () => {
  const validInput = {
    breachTimers: [
      { ticketId: 'TKT-001', slaName: 'Critical — 1h', remainingSeconds: 1800, status: 'warning' as const },
    ],
    escalations: [
      { id: 'esc-1', ticketId: 'TKT-001', level: 1, reason: 'SLA breach', escalatedAt: '2026-01-01T00:00:00Z' },
    ],
    activeSLAs: [
      { id: 'critical', name: 'Critical', targetSeconds: 3600, activeCount: 2, breachCount: 1 },
    ],
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeSlaWarRoom(validInput)
    expect(result).toHaveProperty('breachTimers')
    expect(result).toHaveProperty('escalations')
    expect(result).toHaveProperty('activeSLAs')
    expect(result.breachTimers).toHaveLength(1)
    expect(result.escalations).toHaveLength(1)
    expect(result.activeSLAs).toHaveLength(1)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeSlaWarRoom(null as unknown as Record<string, unknown>)
    expect(result.breachTimers).toEqual([])
    expect(result.escalations).toEqual([])
    expect(result.activeSLAs).toEqual([])
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeSlaWarRoom('nope' as unknown as Record<string, unknown>)
    expect(result.breachTimers).toEqual([])
  })

  it('handles missing fields gracefully', () => {
    const result = normalizeSlaWarRoom({})
    expect(result.breachTimers).toEqual([])
    expect(result.escalations).toEqual([])
    expect(result.activeSLAs).toEqual([])
  })
})

// =========================================================================
// normalizeKnowledgeVault
// =========================================================================

describe('normalizeKnowledgeVault', () => {
  const validInput = {
    articles: [
      { id: 'KB-001', title: 'SOP', excerpt: 'Step-by-step', category: 'SOPs', tags: ['bgp'], updatedAt: '2026-01-01T00:00:00Z' },
    ],
    categories: ['SOPs', 'Playbooks'],
    searchSuggestions: ['bgp', 'ddos'],
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeKnowledgeVault(validInput)
    expect(result).toHaveProperty('articles')
    expect(result).toHaveProperty('categories')
    expect(result).toHaveProperty('searchSuggestions')
    expect(result.articles).toHaveLength(1)
    expect(result.categories).toHaveLength(2)
    expect(result.searchSuggestions).toHaveLength(2)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeKnowledgeVault(null as unknown as Record<string, unknown>)
    expect(result.articles).toEqual([])
    expect(result.categories).toEqual([])
    expect(result.searchSuggestions).toEqual([])
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeKnowledgeVault(false as unknown as Record<string, unknown>)
    expect(result.articles).toEqual([])
  })

  it('handles missing fields gracefully', () => {
    const result = normalizeKnowledgeVault({})
    expect(result.articles).toEqual([])
    expect(result.categories).toEqual([])
    expect(result.searchSuggestions).toEqual([])
  })
})

// =========================================================================
// normalizeAgentGovernance
// =========================================================================

describe('normalizeAgentGovernance', () => {
  const validInput = {
    agents: [
      { id: 'ag-1', name: 'Ana López', status: 'active' as const, lastHeartbeat: '2026-01-01T00:00:00Z' },
    ],
    permissions: [
      { agentId: 'ag-1', scopes: ['tickets:read'] },
    ],
    compliance: { passed: 6, failed: 2, lastCheck: '2026-01-01T00:00:00Z' },
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeAgentGovernance(validInput)
    expect(result).toHaveProperty('agents')
    expect(result).toHaveProperty('permissions')
    expect(result).toHaveProperty('compliance')
    expect(result.agents).toHaveLength(1)
    expect(result.permissions).toHaveLength(1)
    expect(result.compliance.passed).toBe(6)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeAgentGovernance(null as unknown as Record<string, unknown>)
    expect(result.agents).toEqual([])
    expect(result.permissions).toEqual([])
    expect(result.compliance).toEqual({ passed: 0, failed: 0, lastCheck: '' })
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeAgentGovernance(0 as unknown as Record<string, unknown>)
    expect(result.agents).toEqual([])
    expect(result.compliance.passed).toBe(0)
  })

  it('handles missing compliance gracefully', () => {
    const result = normalizeAgentGovernance({ agents: [] })
    expect(result.compliance).toEqual({ passed: 0, failed: 0, lastCheck: '' })
  })
})

// =========================================================================
// normalizeReporting
// =========================================================================

describe('normalizeReporting', () => {
  const validInput = {
    metrics: [
      { label: 'Total Tickets', value: 1284 },
    ],
    trends: [
      { date: '2026-01-01', value: 45, metric: 'tickets' },
    ],
    reportTypes: ['daily', 'weekly'],
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeReporting(validInput)
    expect(result).toHaveProperty('metrics')
    expect(result).toHaveProperty('trends')
    expect(result).toHaveProperty('reportTypes')
    expect(result.metrics).toHaveLength(1)
    expect(result.trends).toHaveLength(1)
    expect(result.reportTypes).toHaveLength(2)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeReporting(null as unknown as Record<string, unknown>)
    expect(result.metrics).toEqual([])
    expect(result.trends).toEqual([])
    expect(result.reportTypes).toEqual([])
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeReporting('x' as unknown as Record<string, unknown>)
    expect(result.metrics).toEqual([])
  })

  it('handles empty arrays gracefully', () => {
    const result = normalizeReporting({ metrics: [], trends: [], reportTypes: [] })
    expect(result.metrics).toEqual([])
    expect(result.trends).toEqual([])
    expect(result.reportTypes).toEqual([])
  })
})

// =========================================================================
// normalizeAudit
// =========================================================================

describe('normalizeAudit', () => {
  const validInput = {
    events: [
      { id: 'evt-1', actor: 'Ana López', action: 'ticket.updated', target: 'TKT-001', timestamp: '2026-01-01T00:00:00Z' },
    ],
    actors: ['Ana López', 'Carlos Ruiz'],
    timeRange: { from: '2026-01-01T00:00:00Z', to: '2026-01-02T00:00:00Z' },
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeAudit(validInput)
    expect(result).toHaveProperty('events')
    expect(result).toHaveProperty('actors')
    expect(result).toHaveProperty('timeRange')
    expect(result.events).toHaveLength(1)
    expect(result.actors).toHaveLength(2)
    expect(result.timeRange.from).toBe('2026-01-01T00:00:00Z')
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeAudit(null as unknown as Record<string, unknown>)
    expect(result.events).toEqual([])
    expect(result.actors).toEqual([])
    expect(result.timeRange).toEqual({ from: '', to: '' })
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeAudit(undefined as unknown as Record<string, unknown>)
    expect(result.events).toEqual([])
    expect(result.timeRange.from).toBe('')
  })

  it('handles missing timeRange gracefully', () => {
    const result = normalizeAudit({ events: [] })
    expect(result.timeRange).toEqual({ from: '', to: '' })
  })
})

// =========================================================================
// normalizeConfiguration
// =========================================================================

describe('normalizeConfiguration', () => {
  const validInput = {
    settings: [
      { key: 'org_name', value: 'Fedeto', type: 'string' as const },
    ],
    thresholds: [
      { name: 'Critical SLA', warning: 1800, critical: 600 },
    ],
    featureFlags: [
      { key: 'dark_mode', enabled: false },
    ],
  }

  it('returns expected shape with valid input', () => {
    const result = normalizeConfiguration(validInput)
    expect(result).toHaveProperty('settings')
    expect(result).toHaveProperty('thresholds')
    expect(result).toHaveProperty('featureFlags')
    expect(result.settings).toHaveLength(1)
    expect(result.thresholds).toHaveLength(1)
    expect(result.featureFlags).toHaveLength(1)
  })

  it('returns fallback when null is passed', () => {
    const result = normalizeConfiguration(null as unknown as Record<string, unknown>)
    expect(result.settings).toEqual([])
    expect(result.thresholds).toEqual([])
    expect(result.featureFlags).toEqual([])
  })

  it('returns fallback for non-object input', () => {
    const result = normalizeConfiguration('config' as unknown as Record<string, unknown>)
    expect(result.settings).toEqual([])
    expect(result.thresholds).toEqual([])
  })

  it('handles missing fields gracefully', () => {
    const result = normalizeConfiguration({})
    expect(result.settings).toEqual([])
    expect(result.thresholds).toEqual([])
    expect(result.featureFlags).toEqual([])
  })
})
