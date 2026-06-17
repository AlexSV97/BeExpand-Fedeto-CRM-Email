/**
 * normalizeTicketCopilot — transforms raw API payload into TicketCopilotView.
 */

// ── View model ──

interface TicketCopilotView {
  conversation: CopilotMessageView[]
  suggestedActions: SuggestionItemView[]
  ticketContext: TicketContextView
}

interface CopilotMessageView {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

interface SuggestionItemView {
  id: string
  label: string
  action: string
}

interface TicketContextView {
  ticketId: string
  subject: string
  status: string
  priority: string
  queue?: string | null
  assignee?: string | null
  customerEmail?: string | null
  slaName?: string | null
  articleCount: number
}

// ── Normalizer ──

function normalizeTicketCopilot(raw: Record<string, unknown>): TicketCopilotView {
  if (!raw || typeof raw !== 'object') {
    return {
      conversation: [],
      suggestedActions: [],
      ticketContext: { ticketId: '', subject: '', status: '', priority: 'medium', articleCount: 0 },
    }
  }
  return {
    conversation: (raw.conversation as CopilotMessageView[]) ?? [],
    suggestedActions: (raw.suggestedActions as SuggestionItemView[]) ?? [],
    ticketContext: (raw.ticketContext as TicketContextView) ?? {
      ticketId: '', subject: '', status: '', priority: 'medium', articleCount: 0,
    },
  }
}

export { normalizeTicketCopilot }
export type { TicketCopilotView, CopilotMessageView, SuggestionItemView, TicketContextView }
