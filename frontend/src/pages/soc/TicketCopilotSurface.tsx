/**
 * TicketCopilotSurface — split-view AI copilot for working on a ticket.
 *
 * Left panel: ticket detail with conversation timeline.
 * Right panel: AI copilot with suggested actions, auto-reply drafts,
 * context summary, and escalation options.
 */

import { useState, useEffect, useCallback } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { normalizeTicketCopilot } from '../../services/soc/normalize/ticketCopilot'
import type {
  TicketCopilotView,
  CopilotMessageView,
  SuggestionItemView,
} from '../../services/soc/normalize/ticketCopilot'
import { SocLoadingState, SocErrorState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import { getSelectedTicketId } from './SmartTicketQueueSurface'
import {
  ArrowLeft,
  Bot,
  MessageSquare,
  Send,
  ArrowUpRight,
  PenSquare,
  User,
  Sparkles,
  Clock,
  Shield,
  Flag,
  FileText,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.TICKET_COPILOT
const FALLBACK_TICKET_ID = 'TKT-1001'

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function statusBadgeClass(status: string): string {
  switch (status.toLowerCase()) {
    case 'open':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'in_progress':
    case 'in progress':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'resolved':
      return 'bg-success/10 text-success border-success/20'
    case 'closed':
      return 'bg-muted text-muted-foreground border-border/50'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

function priorityBadgeClass(priority: string): string {
  switch (priority.toLowerCase()) {
    case 'critical':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    case 'high':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'medium':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'low':
      return 'bg-muted text-muted-foreground border-border/50'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────

function ConversationMessage({ msg }: { msg: CopilotMessageView }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3',
        isSystem && 'bg-muted/30',
      )}
    >
      <div
        className={cn(
          'mt-0.5 rounded-full p-1.5 shrink-0',
          isUser
            ? 'bg-chart-1/10 text-chart-1'
            : isSystem
              ? 'bg-muted text-muted-foreground'
              : 'bg-primary/10 text-primary',
        )}
      >
        {isUser ? (
          <User className="h-3 w-3" />
        ) : isSystem ? (
          <Shield className="h-3 w-3" />
        ) : (
          <Bot className="h-3 w-3" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-foreground">
            {isUser ? t('copilot.you') : isSystem ? t('copilot.system') : t('copilot.assistant')}
          </span>
          <span className="text-[10px] text-muted-foreground">{formatTimestamp(msg.timestamp)}</span>
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
          {applyNeutralCopy(msg.content)}
        </p>
      </div>
    </div>
  )
}

function SuggestionCard({
  suggestion,
  onApply,
}: {
  suggestion: SuggestionItemView
  onApply: (s: SuggestionItemView) => void
}) {
  return (
    <div className="group flex items-start gap-3 px-4 py-3 border border-border/30 rounded-xl hover:border-border/60 hover:bg-muted/30 transition-all">
      <Sparkles className="h-4 w-4 text-chart-2 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground font-medium">{applyNeutralCopy(suggestion.label)}</p>
        <p className="text-xs text-muted-foreground mt-0.5 font-mono">{suggestion.action}</p>
      </div>
      <button
        onClick={() => onApply(suggestion)}
        className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-xs font-medium text-primary hover:underline cursor-pointer"
      >
        {t('copilot.apply')}
      </button>
    </div>
  )
}

// ─── Mock fallback conversations (for demo / resilience) ──────────────────

function buildMockCopilot(ticketId: string): TicketCopilotView {
  return {
    conversation: [
      {
        role: 'system',
        content: `Ticket ${ticketId} opened for ${applyNeutralCopy('circuit latency on MX-480 edge router')}. Priority: High. Assigned to Network Ops.`,
        timestamp: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        role: 'assistant',
        content: applyNeutralCopy('I\'ve analysed the recent BGP logs for this circuit. There\'s a pattern of route flapping starting around 02:30 UTC. Recommended: check peer AS 64512 for recent config changes.'),
        timestamp: new Date(Date.now() - 1800000).toISOString(),
      },
      {
        role: 'user',
        content: applyNeutralCopy('Confirmed — peer AS64512 had a maintenance window last night. Rolling back the BGP community change.'),
        timestamp: new Date(Date.now() - 600000).toISOString(),
      },
      {
        role: 'assistant',
        content: applyNeutralCopy('Good catch. After rollback, monitor the circuit for 30 min and verify the flap count drops to zero. I\'ll draft the post-mortem summary.'),
        timestamp: new Date(Date.now() - 300000).toISOString(),
      },
    ],
    suggestedActions: [
      { id: 's1', label: applyNeutralCopy('Apply BGP rollback command'), action: 'apply_bgp_rollback' },
      { id: 's2', label: applyNeutralCopy('Draft post-mortem summary'), action: 'draft_post_mortem' },
      { id: 's3', label: applyNeutralCopy('Notify affected customers'), action: 'notify_customers' },
      { id: 's4', label: applyNeutralCopy('Escalate to Tier-3 NOC'), action: 'escalate_tier3' },
    ],
    ticketContext: {
      ticketId,
      subject: applyNeutralCopy('Circuit latency on MX-480 edge router — possible BGP flap'),
      status: 'in_progress',
    },
  }
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function TicketCopilotSurface() {
  const { goBack, setSurfaceStatus } = useSocShell()

  // Resolve ticket ID from module-level state or fallback
  const ticketId = getSelectedTicketId() ?? FALLBACK_TICKET_ID

  const [data, setData] = useState<TicketCopilotView | null>(null)
  const [error, setError] = useState<SocError | null>(null)
  const [loading, setLoading] = useState(true)

  // ── Fetch data ────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSurfaceStatus(SURFACE_ID, 'loading')

    try {
      const endpoint = SOC_ENDPOINTS[SURFACE_ID].replace(':id', ticketId)
      const raw = await socFetch<Record<string, unknown>>(endpoint)
      const normalized = normalizeTicketCopilot(raw)
      setData(normalized)
      setSurfaceStatus(SURFACE_ID, 'ready')
    } catch (err: unknown) {
      // Fallback: if the backend is not available, use mock data
      // (same resilience pattern as Dashboard.tsx)
      const mockData = buildMockCopilot(ticketId)
      setData(mockData)
      setSurfaceStatus(SURFACE_ID, 'ready')

      // Still register a soft error so the user knows data is mocked
      const socErr: SocError = {
        code: 'FALLBACK_MODE',
        message: err instanceof Error ? err.message : String(err),
      }
      setError(socErr)
    } finally {
      setLoading(false)
    }
  }, [ticketId, setSurfaceStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Handlers ──────────────────────────────────────────────────────

  const handleApplySuggestion = (suggestion: SuggestionItemView) => {
    // In a real implementation, this would call the API
    // For now, it's a UI-only action
    console.log(`[TicketCopilot] Apply suggestion: ${suggestion.action}`)
  }

  const handleReclassification = () => {
    console.log('[TicketCopilot] Request reclassification')
  }

  const handleEscalate = () => {
    console.log('[TicketCopilot] Escalate ticket')
  }

  const handleAddNote = () => {
    console.log('[TicketCopilot] Add note')
  }

  // ── Loading ───────────────────────────────────────────────────────

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.ticketCopilot')} />
  }

  // ── Hard error (no data at all) ───────────────────────────────────

  if (error && !data) {
    return <SocErrorState error={error} />
  }

  // ── Content ───────────────────────────────────────────────────────

  const ctx = data?.ticketContext
  const isFallback = error?.code === 'FALLBACK_MODE'

  return (
    <div className="space-y-4">
      {/* Back button + header */}
      <div className="flex items-center gap-3">
        <button
          onClick={goBack}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('copilot.back')}
        </button>
        <div className="h-4 w-px bg-border" />
        <h2 className="text-lg font-semibold">
          {ctx?.subject ? applyNeutralCopy(ctx.subject) : t('surfaces.ticketCopilot')}
        </h2>
        {isFallback && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
            {t('copilot.fallbackMode')}
          </span>
        )}
      </div>

      {/* Status bar */}
      {ctx && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-2.5">
          <span className="font-mono font-medium text-foreground">{ctx.ticketId}</span>
          <div className="h-3 w-px bg-border" />
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', statusBadgeClass(ctx.status))}>
            {t(`ticket.status.${ctx.status.toLowerCase()}`)}
          </span>
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', priorityBadgeClass(data?.ticketContext?.status ?? ''))}>
            {t('ticket.priority.high')}
          </span>
        </div>
      )}

      {/* Grid: Left + Right panels */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── Left panel: Ticket Detail ──────────────────────────── */}
        <div className="lg:col-span-3 space-y-4">
          {/* Conversation timeline */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
              <MessageSquare className="h-4 w-4 text-chart-1" />
              <h3 className="text-sm font-semibold">{t('copilot.conversation')}</h3>
              <span className="ml-auto text-xs text-muted-foreground">
                {data?.conversation.length ?? 0} {t('copilot.messages')}
              </span>
            </div>
            <div className="divide-y divide-border/20 max-h-[420px] overflow-y-auto">
              {data?.conversation.map((msg, i) => (
                <ConversationMessage key={`${msg.role}-${i}`} msg={msg} />
              ))}
            </div>

            {/* Quick reply input */}
            <div className="flex items-center gap-2 border-t border-border/30 px-4 py-3">
              <input
                type="text"
                placeholder={t('copilot.replyPlaceholder')}
                className="flex-1 text-sm bg-muted/50 border border-border/50 rounded-lg px-3 py-2 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <button className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Activity timeline (extra context) */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">{t('copilot.activity')}</h3>
            </div>
            <div className="px-5 py-4 space-y-3">
              {/* These would come from the API in a real implementation */}
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-chart-1/50" />
                <span className="text-muted-foreground">{applyNeutralCopy('Ticket assigned to Network Operations')}</span>
                <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{t('time.hoursAgo', { count: '2' })}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-chart-2/50" />
                <span className="text-muted-foreground">{applyNeutralCopy('BGP log analysis requested')}</span>
                <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{t('time.hoursAgo', { count: '1' })}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-warning/50" />
                <span className="text-muted-foreground">{applyNeutralCopy('SLA warning: 2h remaining before breach')}</span>
                <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{t('time.minAgo', { count: '30' })}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Right panel: AI Copilot ───────────────────────────── */}
        <div className="lg:col-span-2 space-y-4">
          {/* Suggested actions */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
              <Sparkles className="h-4 w-4 text-chart-2" />
              <h3 className="text-sm font-semibold">{t('copilot.suggestedActions')}</h3>
            </div>
            <div className="p-3 space-y-2">
              {data?.suggestedActions.map((s) => (
                <SuggestionCard
                  key={s.id}
                  suggestion={s}
                  onApply={handleApplySuggestion}
                />
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
              <Flag className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">{t('copilot.actions')}</h3>
            </div>
            <div className="p-4 space-y-2">
              <button
                onClick={handleReclassification}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-border/50 hover:border-border hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <PenSquare className="h-4 w-4 text-chart-1" />
                {t('copilot.reclassify')}
              </button>
              <button
                onClick={handleEscalate}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-border/50 hover:border-border hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <ArrowUpRight className="h-4 w-4 text-warning" />
                {t('copilot.escalate')}
              </button>
              <button
                onClick={handleAddNote}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-border/50 hover:border-border hover:bg-muted/50 transition-colors cursor-pointer"
              >
                <FileText className="h-4 w-4 text-muted-foreground" />
                {t('copilot.addNote')}
              </button>
            </div>
          </div>

          {/* Context summary */}
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
              <Bot className="h-4 w-4 text-chart-2" />
              <h3 className="text-sm font-semibold">{t('copilot.contextSummary')}</h3>
            </div>
            <div className="p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('copilot.ticketId')}</span>
                <span className="font-mono font-medium">{ctx?.ticketId ?? ticketId}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('copilot.status')}</span>
                <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', statusBadgeClass(ctx?.status ?? 'open'))}>
                  {t(`ticket.status.${(ctx?.status ?? 'open').toLowerCase()}`)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('copilot.conversationAge')}</span>
                <span className="text-foreground">{data?.conversation.length ?? 0} {t('copilot.messages')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">{t('copilot.assignedTo')}</span>
                <span className="text-foreground">{t('copilot.networkOps')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
