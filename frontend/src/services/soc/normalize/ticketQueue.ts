/**
 * normalizeTicketQueue — transforms raw API payload into TicketQueueView.
 */

// ── View model ──

interface TicketQueueView {
  tickets: TicketItemView[]
  total: number
  page: number
  filters: TicketFiltersView
}

interface TicketItemView {
  id: string
  subject: string
  status: string
  priority: string
  assignee?: string
  createdAt: string
  updatedAt: string
}

interface TicketFiltersView {
  status?: string[]
  priority?: string[]
  assignee?: string[]
}

// ── Normalizer ──

function normalizeTicketQueue(raw: Record<string, unknown>): TicketQueueView {
  if (!raw || typeof raw !== 'object') {
    return { tickets: [], total: 0, page: 1, filters: {} }
  }
  return {
    tickets: (raw.tickets as TicketItemView[]) ?? [],
    total: (raw.total as number) ?? 0,
    page: (raw.page as number) ?? 1,
    filters: (raw.filters as TicketFiltersView) ?? {},
  }
}

export { normalizeTicketQueue }
export type { TicketQueueView, TicketItemView, TicketFiltersView }
