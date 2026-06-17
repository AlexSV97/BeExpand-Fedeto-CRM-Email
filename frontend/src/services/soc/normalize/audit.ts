/**
 * normalizeAudit — transforms raw API payload into AuditView.
 */

// ── View model ──

interface AuditView {
  events: AuditEventView[]
  actors: string[]
  timeRange: AuditTimeRange
}

interface AuditEventView {
  id: string
  actor: string
  action: string
  target: string
  timestamp: string
  details?: Record<string, unknown>
}

interface AuditTimeRange {
  from: string
  to: string
}

// ── Normalizer ──

function normalizeAudit(raw: Record<string, unknown>): AuditView {
  if (!raw || typeof raw !== 'object') {
    return { events: [], actors: [], timeRange: { from: '', to: '' } }
  }
  return {
    events: (raw.events as AuditEventView[]) ?? [],
    actors: (raw.actors as string[]) ?? [],
    timeRange: (raw.timeRange as AuditTimeRange) ?? { from: '', to: '' },
  }
}

export { normalizeAudit }
export type { AuditView, AuditEventView, AuditTimeRange }
