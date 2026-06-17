/**
 * Tests for mock data validity.
 *
 * Verifies that ALL mock data constants in mockData.ts are:
 * - Properly typed (no null/undefined where typed as non-null)
 * - Contain non-empty arrays where expected
 * - Have the correct structure matching the view models
 */

import { describe, it, expect } from 'vitest'
import {
  MOCK_COMMAND_CENTER,
  MOCK_TICKET_QUEUE,
  MOCK_TICKET_COPILOT,
  MOCK_SLA_WAR_ROOM,
  MOCK_KNOWLEDGE_VAULT,
  MOCK_AGENT_GOVERNANCE,
  MOCK_REPORTING,
  MOCK_AUDIT,
  MOCK_CONFIGURATION,
  MOCK_DATA_REGISTRY,
} from '../mockData'
import { SURFACE_IDS } from '../contracts'

// =========================================================================
// Registry
// =========================================================================

describe('MOCK_DATA_REGISTRY', () => {
  it('has entries for all 9 surfaces', () => {
    const surfaceIds = Object.values(SURFACE_IDS)
    const registrySurfaceIds = MOCK_DATA_REGISTRY.map((e) => e.surfaceId)
    for (const id of surfaceIds) {
      expect(registrySurfaceIds).toContain(id)
    }
  })

  it('has unique surface IDs', () => {
    const ids = MOCK_DATA_REGISTRY.map((e) => e.surfaceId)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('every entry has endpoint, surfaceId, and mockData', () => {
    for (const entry of MOCK_DATA_REGISTRY) {
      expect(entry.endpoint).toBeDefined()
      expect(typeof entry.endpoint).toBe('string')
      expect(entry.endpoint.startsWith('/soc/')).toBe(true)
      expect(entry.surfaceId).toBeDefined()
      expect(entry.mockData).toBeDefined()
    }
  })
})

// =========================================================================
// MOCK_COMMAND_CENTER
// =========================================================================

describe('MOCK_COMMAND_CENTER', () => {
  it('has kpiCards, recentAlerts, queuePressure, surfaceStatus', () => {
    expect(MOCK_COMMAND_CENTER.kpiCards).toBeDefined()
    expect(MOCK_COMMAND_CENTER.recentAlerts).toBeDefined()
    expect(typeof MOCK_COMMAND_CENTER.queuePressure).toBe('number')
    expect(typeof MOCK_COMMAND_CENTER.surfaceStatus).toBe('string')
  })

  it('has non-empty kpiCards', () => {
    expect(MOCK_COMMAND_CENTER.kpiCards.length).toBeGreaterThan(0)
  })

  it('has non-empty recentAlerts', () => {
    expect(MOCK_COMMAND_CENTER.recentAlerts.length).toBeGreaterThan(0)
  })

  it('every kpiCard has label, value, trend', () => {
    for (const card of MOCK_COMMAND_CENTER.kpiCards) {
      expect(card).toHaveProperty('label')
      expect(typeof card.label).toBe('string')
      expect(card).toHaveProperty('value')
      expect(typeof card.value).toBe('number')
      expect(card).toHaveProperty('trend')
      expect(['up', 'down', 'stable']).toContain(card.trend)
    }
  })

  it('every alert has id, severity, message, timestamp', () => {
    for (const alert of MOCK_COMMAND_CENTER.recentAlerts) {
      expect(alert).toHaveProperty('id')
      expect(alert).toHaveProperty('severity')
      expect(['critical', 'warning', 'info']).toContain(alert.severity)
      expect(alert).toHaveProperty('message')
      expect(alert).toHaveProperty('timestamp')
    }
  })
})

// =========================================================================
// MOCK_TICKET_QUEUE
// =========================================================================

describe('MOCK_TICKET_QUEUE', () => {
  it('has tickets, total, page, filters', () => {
    expect(Array.isArray(MOCK_TICKET_QUEUE.tickets)).toBe(true)
    expect(typeof MOCK_TICKET_QUEUE.total).toBe('number')
    expect(typeof MOCK_TICKET_QUEUE.page).toBe('number')
    expect(MOCK_TICKET_QUEUE.filters).toHaveProperty('status')
    expect(MOCK_TICKET_QUEUE.filters).toHaveProperty('priority')
  })

  it('has non-empty tickets', () => {
    expect(MOCK_TICKET_QUEUE.tickets.length).toBeGreaterThan(0)
  })

  it('every ticket has required fields', () => {
    for (const t of MOCK_TICKET_QUEUE.tickets) {
      expect(t).toHaveProperty('id')
      expect(t).toHaveProperty('subject')
      expect(t).toHaveProperty('status')
      expect(t).toHaveProperty('priority')
      expect(t).toHaveProperty('createdAt')
      expect(t).toHaveProperty('updatedAt')
    }
  })

  it('total matches tickets array length', () => {
    expect(MOCK_TICKET_QUEUE.total).toBe(MOCK_TICKET_QUEUE.tickets.length)
  })
})

// =========================================================================
// MOCK_TICKET_COPILOT
// =========================================================================

describe('MOCK_TICKET_COPILOT', () => {
  it('has conversation, suggestedActions, ticketContext', () => {
    expect(Array.isArray(MOCK_TICKET_COPILOT.conversation)).toBe(true)
    expect(Array.isArray(MOCK_TICKET_COPILOT.suggestedActions)).toBe(true)
    expect(MOCK_TICKET_COPILOT.ticketContext).toHaveProperty('ticketId')
    expect(MOCK_TICKET_COPILOT.ticketContext).toHaveProperty('subject')
    expect(MOCK_TICKET_COPILOT.ticketContext).toHaveProperty('status')
  })

  it('has non-empty conversation', () => {
    expect(MOCK_TICKET_COPILOT.conversation.length).toBeGreaterThan(0)
  })

  it('has non-empty suggestedActions', () => {
    expect(MOCK_TICKET_COPILOT.suggestedActions.length).toBeGreaterThan(0)
  })

  it('every message has role, content, timestamp', () => {
    for (const msg of MOCK_TICKET_COPILOT.conversation) {
      expect(['user', 'assistant', 'system']).toContain(msg.role)
      expect(typeof msg.content).toBe('string')
      expect(typeof msg.timestamp).toBe('string')
    }
  })

  it('every suggestion has id, label, action', () => {
    for (const s of MOCK_TICKET_COPILOT.suggestedActions) {
      expect(s).toHaveProperty('id')
      expect(s).toHaveProperty('label')
      expect(s).toHaveProperty('action')
    }
  })
})

// =========================================================================
// MOCK_SLA_WAR_ROOM
// =========================================================================

describe('MOCK_SLA_WAR_ROOM', () => {
  it('has breachTimers, escalations, activeSLAs', () => {
    expect(Array.isArray(MOCK_SLA_WAR_ROOM.breachTimers)).toBe(true)
    expect(Array.isArray(MOCK_SLA_WAR_ROOM.escalations)).toBe(true)
    expect(Array.isArray(MOCK_SLA_WAR_ROOM.activeSLAs)).toBe(true)
  })

  it('has non-empty breachTimers', () => {
    expect(MOCK_SLA_WAR_ROOM.breachTimers.length).toBeGreaterThan(0)
  })

  it('every breachTimer has required fields', () => {
    for (const t of MOCK_SLA_WAR_ROOM.breachTimers) {
      expect(t).toHaveProperty('ticketId')
      expect(t).toHaveProperty('slaName')
      expect(typeof t.remainingSeconds).toBe('number')
      expect(['ok', 'warning', 'breached']).toContain(t.status)
    }
  })

  it('every escalation has id, ticketId, level, reason', () => {
    for (const e of MOCK_SLA_WAR_ROOM.escalations) {
      expect(e).toHaveProperty('id')
      expect(e).toHaveProperty('ticketId')
      expect(typeof e.level).toBe('number')
      expect(e).toHaveProperty('reason')
      expect(e).toHaveProperty('escalatedAt')
    }
  })

  it('every activeSLA has required fields', () => {
    for (const sla of MOCK_SLA_WAR_ROOM.activeSLAs) {
      expect(sla).toHaveProperty('id')
      expect(sla).toHaveProperty('name')
      expect(typeof sla.targetSeconds).toBe('number')
      expect(typeof sla.activeCount).toBe('number')
      expect(typeof sla.breachCount).toBe('number')
    }
  })
})

// =========================================================================
// MOCK_KNOWLEDGE_VAULT
// =========================================================================

describe('MOCK_KNOWLEDGE_VAULT', () => {
  it('has articles, categories, searchSuggestions', () => {
    expect(Array.isArray(MOCK_KNOWLEDGE_VAULT.articles)).toBe(true)
    expect(Array.isArray(MOCK_KNOWLEDGE_VAULT.categories)).toBe(true)
    expect(Array.isArray(MOCK_KNOWLEDGE_VAULT.searchSuggestions)).toBe(true)
  })

  it('has non-empty articles', () => {
    expect(MOCK_KNOWLEDGE_VAULT.articles.length).toBeGreaterThan(0)
  })

  it('every article has required fields', () => {
    for (const a of MOCK_KNOWLEDGE_VAULT.articles) {
      expect(a).toHaveProperty('id')
      expect(a).toHaveProperty('title')
      expect(a).toHaveProperty('excerpt')
      expect(a).toHaveProperty('category')
      expect(Array.isArray(a.tags)).toBe(true)
      expect(a).toHaveProperty('updatedAt')
    }
  })
})

// =========================================================================
// MOCK_AGENT_GOVERNANCE
// =========================================================================

describe('MOCK_AGENT_GOVERNANCE', () => {
  it('has agents, permissions, compliance', () => {
    expect(Array.isArray(MOCK_AGENT_GOVERNANCE.agents)).toBe(true)
    expect(Array.isArray(MOCK_AGENT_GOVERNANCE.permissions)).toBe(true)
    expect(MOCK_AGENT_GOVERNANCE.compliance).toHaveProperty('passed')
    expect(MOCK_AGENT_GOVERNANCE.compliance).toHaveProperty('failed')
    expect(MOCK_AGENT_GOVERNANCE.compliance).toHaveProperty('lastCheck')
  })

  it('has non-empty agents', () => {
    expect(MOCK_AGENT_GOVERNANCE.agents.length).toBeGreaterThan(0)
  })

  it('every agent has required fields', () => {
    for (const a of MOCK_AGENT_GOVERNANCE.agents) {
      expect(a).toHaveProperty('id')
      expect(a).toHaveProperty('name')
      expect(['active', 'paused', 'error']).toContain(a.status)
      expect(a).toHaveProperty('lastHeartbeat')
    }
  })

  it('compliance has numbers for passed/failed', () => {
    expect(typeof MOCK_AGENT_GOVERNANCE.compliance.passed).toBe('number')
    expect(typeof MOCK_AGENT_GOVERNANCE.compliance.failed).toBe('number')
  })
})

// =========================================================================
// MOCK_REPORTING
// =========================================================================

describe('MOCK_REPORTING', () => {
  it('has metrics, trends, reportTypes', () => {
    expect(Array.isArray(MOCK_REPORTING.metrics)).toBe(true)
    expect(Array.isArray(MOCK_REPORTING.trends)).toBe(true)
    expect(Array.isArray(MOCK_REPORTING.reportTypes)).toBe(true)
  })

  it('has non-empty metrics', () => {
    expect(MOCK_REPORTING.metrics.length).toBeGreaterThan(0)
  })

  it('every metric has label and value', () => {
    for (const m of MOCK_REPORTING.metrics) {
      expect(m).toHaveProperty('label')
      expect(typeof m.value).toBe('number')
    }
  })

  it('every trend has date, value, metric', () => {
    for (const t of MOCK_REPORTING.trends) {
      expect(t).toHaveProperty('date')
      expect(typeof t.value).toBe('number')
      expect(t).toHaveProperty('metric')
    }
  })
})

// =========================================================================
// MOCK_AUDIT
// =========================================================================

describe('MOCK_AUDIT', () => {
  it('has events, actors, timeRange', () => {
    expect(Array.isArray(MOCK_AUDIT.events)).toBe(true)
    expect(Array.isArray(MOCK_AUDIT.actors)).toBe(true)
    expect(MOCK_AUDIT.timeRange).toHaveProperty('from')
    expect(MOCK_AUDIT.timeRange).toHaveProperty('to')
  })

  it('has non-empty events', () => {
    expect(MOCK_AUDIT.events.length).toBeGreaterThan(0)
  })

  it('every event has required fields', () => {
    for (const e of MOCK_AUDIT.events) {
      expect(e).toHaveProperty('id')
      expect(e).toHaveProperty('actor')
      expect(e).toHaveProperty('action')
      expect(e).toHaveProperty('target')
      expect(e).toHaveProperty('timestamp')
    }
  })
})

// =========================================================================
// MOCK_CONFIGURATION
// =========================================================================

describe('MOCK_CONFIGURATION', () => {
  it('has settings, thresholds, featureFlags', () => {
    expect(Array.isArray(MOCK_CONFIGURATION.settings)).toBe(true)
    expect(Array.isArray(MOCK_CONFIGURATION.thresholds)).toBe(true)
    expect(Array.isArray(MOCK_CONFIGURATION.featureFlags)).toBe(true)
  })

  it('has non-empty settings', () => {
    expect(MOCK_CONFIGURATION.settings.length).toBeGreaterThan(0)
  })

  it('every setting has key, value, type', () => {
    for (const s of MOCK_CONFIGURATION.settings) {
      expect(s).toHaveProperty('key')
      expect(s).toHaveProperty('value')
      expect(['string', 'number', 'boolean', 'json']).toContain(s.type)
    }
  })

  it('every threshold has name, warning, critical', () => {
    for (const t of MOCK_CONFIGURATION.thresholds) {
      expect(t).toHaveProperty('name')
      expect(typeof t.warning).toBe('number')
      expect(typeof t.critical).toBe('number')
    }
  })

  it('every featureFlag has key and enabled', () => {
    for (const f of MOCK_CONFIGURATION.featureFlags) {
      expect(f).toHaveProperty('key')
      expect(typeof f.enabled).toBe('boolean')
    }
  })
})
