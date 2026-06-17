/**
 * normalizeSlaWarRoom — transforms raw API payload into SlaWarRoomView.
 */

// ── View model ──

interface SlaWarRoomView {
  breachTimers: BreachTimerView[]
  escalations: EscalationItemView[]
  activeSLAs: SlaItemView[]
}

interface BreachTimerView {
  ticketId: string
  slaName: string
  remainingSeconds: number
  status: 'ok' | 'warning' | 'breached'
}

interface EscalationItemView {
  id: string
  ticketId: string
  level: number
  reason: string
  escalatedAt: string
}

interface SlaItemView {
  id: string
  name: string
  targetSeconds: number
  activeCount: number
  breachCount: number
}

// ── Normalizer ──

function normalizeSlaWarRoom(raw: Record<string, unknown>): SlaWarRoomView {
  if (!raw || typeof raw !== 'object') {
    return { breachTimers: [], escalations: [], activeSLAs: [] }
  }
  return {
    breachTimers: (raw.breachTimers as BreachTimerView[]) ?? [],
    escalations: (raw.escalations as EscalationItemView[]) ?? [],
    activeSLAs: (raw.activeSLAs as SlaItemView[]) ?? [],
  }
}

export { normalizeSlaWarRoom }
export type { SlaWarRoomView, BreachTimerView, EscalationItemView, SlaItemView }
