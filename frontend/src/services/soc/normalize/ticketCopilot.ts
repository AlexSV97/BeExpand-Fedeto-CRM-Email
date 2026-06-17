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
}

// ── Normalizer ──

function normalizeTicketCopilot(raw: Record<string, unknown>): TicketCopilotView {
  if (!raw || typeof raw !== 'object') {
    return { conversation: [], suggestedActions: [], ticketContext: { ticketId: '', subject: '', status: '' } }
  }
  return {
    conversation: (raw.conversation as CopilotMessageView[]) ?? [],
    suggestedActions: (raw.suggestedActions as SuggestionItemView[]) ?? [],
    ticketContext: (raw.ticketContext as TicketContextView) ?? { ticketId: '', subject: '', status: '' },
  }
}

export { normalizeTicketCopilot }
export type { TicketCopilotView, CopilotMessageView, SuggestionItemView, TicketContextView }
