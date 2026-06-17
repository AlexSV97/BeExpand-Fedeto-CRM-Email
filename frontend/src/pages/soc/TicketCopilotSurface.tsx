/**
 * TicketCopilotSurface — split-view AI copilot for working on a ticket.
 *
 * Left panel: ticket detail with conversation timeline.
 * Right panel: AI copilot with suggested actions, auto-reply drafts,
 * context summary, and escalation options.
 */

import { useState, useEffect } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeTicketCopilot } from '../../services/soc/normalize/ticketCopilot'
import type {
  CopilotMessageView,
  SuggestionItemView,
} from '../../services/soc/normalize/ticketCopilot'
import { MOCK_TICKET_COPILOT } from '../../services/soc/mockData'
import { SocLoadingState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import { getSelectedTicketId } from './SmartTicketQueueSurface'
import {
  ArrowLeft,
  ArrowUpRight,
  Bot,
  Check,
  Clock,
  Flag,
  FileText,
  Loader2,
  MessageSquare,
  PenSquare,
  Send,
  Shield,
  Sparkles,
  User,
  X,
  AlertTriangle,
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
    <div className={cn('flex gap-3 px-4 py-3', isSystem && 'bg-muted/30')}>
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

// ─── Main surface ─────────────────────────────────────────────────────────

export default function TicketCopilotSurface() {
  const { goBack } = useSocShell()

  // Resolve ticket ID from module-level state or fallback
  const ticketId = getSelectedTicketId() ?? FALLBACK_TICKET_ID

  // The copilot endpoint uses :id which we resolve here
  const endpoint = SOC_ENDPOINTS[SURFACE_IDS.TICKET_COPILOT].replace(':id', ticketId)

  const { data, loading, error, source, refresh } = useSocResource(
    endpoint,
    normalizeTicketCopilot,
    MOCK_TICKET_COPILOT,
    SURFACE_ID,
  )

  // ── Action state ──────────────────────────────────────────────────

  const [actionLoading, setActionLoading] = useState(false)
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error', message: string } | null>(null)
  const [newNote, setNewNote] = useState('')
  const [showNoteInput, setShowNoteInput] = useState(false)

  // ── Handlers ──────────────────────────────────────────────────────

  async function handleAction(action: string, suggestion?: SuggestionItemView) {
    if (!ticketId) return

    try {
      setActionLoading(true)
      setActionFeedback(null)

      switch (action) {
        case 'apply':
          await socFetch(endpoint, {
            method: 'POST',
            body: JSON.stringify({ action: suggestion?.action, message: suggestion?.label }),
          })
          break

        case 'reclassify':
          await socFetch(`/soc/tickets/${ticketId}/reclassify`, {
            method: 'POST',
            body: JSON.stringify({ reason: suggestion?.action || 'Reclassification requested' }),
          })
          break

        case 'escalate':
          await socFetch(`/soc/tickets/${ticketId}/escalate`, {
            method: 'POST',
            body: JSON.stringify({ reason: suggestion?.action || 'Escalation requested' }),
          })
          break
      }

      setActionFeedback({ type: 'success', message: `${action} executed successfully` })
    } catch (err) {
      setActionFeedback({
        type: 'error',
        message: `Failed to ${action}: ${err instanceof Error ? err.message : 'Unknown error'}`,
      })
    } finally {
      setActionLoading(false)
    }
  }

  const handleApplySuggestion = (suggestion: SuggestionItemView) => {
    handleAction('apply', suggestion)
  }

  const handleReclassification = () => {
    if (!window.confirm('Are you sure you want to reclassify this ticket?')) return
    handleAction('reclassify')
  }

  const handleEscalate = () => {
    if (!window.confirm('Are you sure you want to escalate this ticket?')) return
    handleAction('escalate')
  }

  async function handleAddNote() {
    if (!newNote.trim() || !ticketId) return

    try {
      setActionLoading(true)
      setActionFeedback(null)
      await socFetch(`/soc/tickets/${ticketId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ content: newNote, visibility: 'internal' }),
      })
      setActionFeedback({ type: 'success', message: 'Note added successfully' })
      setNewNote('')
      setShowNoteInput(false)
    } catch (err) {
      setActionFeedback({
        type: 'error',
        message: `Failed to add note: ${err instanceof Error ? err.message : 'Unknown error'}`,
      })
    } finally {
      setActionLoading(false)
    }
  }

  // ── Auto-dismiss feedback ─────────────────────────────────────────

  useEffect(() => {
    if (actionFeedback) {
      const timer = setTimeout(() => setActionFeedback(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [actionFeedback])

  // ── Loading ───────────────────────────────────────────────────────

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.ticketCopilot')} />
  }

  // ── Error ─────────────────────────────────────────────────────────
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Content ───────────────────────────────────────────────────────

  const ctx = data.ticketContext
  const isDemo = source === 'mock'

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
        {isDemo && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-warning/10 text-warning border border-warning/20">
            {"Demo"}
          </span>
        )}
      </div>

      {/* Error fallback banner when API failed */}
      {source === 'error' && (
        <div className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Failed to load data from server. Showing cached/demo data.</span>
          </div>
          <button onClick={refresh} className="underline hover:no-underline cursor-pointer">Retry</button>
        </div>
      )}

      {/* Demo banner when source is mock */}
      {isDemo && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
          <AlertTriangle className="h-3.5 w-3.5" />
          {"Demo mode — data shown from local cache"}
          {error && <span className="ml-auto text-muted-foreground">({error})</span>}
        </div>
      )}

      {/* Status bar */}
      {ctx && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-2.5">
          <span className="font-mono font-medium text-foreground">{ctx.ticketId}</span>
          <div className="h-3 w-px bg-border" />
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', statusBadgeClass(ctx.status))}>
            {t(`ticket.status.${ctx.status.toLowerCase()}`)}
          </span>
          <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', priorityBadgeClass(ctx.priority))}>
            {t(`ticket.priority.${ctx.priority.toLowerCase()}`)}
          </span>
        </div>
      )}

      {ctx && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Queue</p>
            <p className="text-sm font-medium text-foreground mt-1">{ctx.queue || 'Unassigned'}</p>
          </div>
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Assignee</p>
            <p className="text-sm font-medium text-foreground mt-1">{ctx.assignee || 'Unassigned'}</p>
          </div>
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">SLA</p>
            <p className="text-sm font-medium text-foreground mt-1">{ctx.slaName || 'No SLA'}</p>
          </div>
          <div className="bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-3">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Articles</p>
            <p className="text-sm font-medium text-foreground mt-1">{ctx.articleCount}</p>
          </div>
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
                {data.conversation.length} {t('copilot.messages')}
              </span>
            </div>
            <div className="divide-y divide-border/20 max-h-[420px] overflow-y-auto">
              {data.conversation.map((msg, i) => (
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
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-chart-1/50" />
                <span className="text-muted-foreground">{applyNeutralCopy(`Ticket assigned to ${ctx?.assignee || 'the response queue'}`)}</span>
                <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{t('time.hoursAgo', { count: '2' })}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-chart-2/50" />
                <span className="text-muted-foreground">{applyNeutralCopy(`Queue context: ${ctx?.queue || 'unassigned queue'}`)}</span>
                <span className="ml-auto text-[10px] text-muted-foreground shrink-0">{t('time.hoursAgo', { count: '1' })}</span>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-warning/50" />
                <span className="text-muted-foreground">{applyNeutralCopy(`SLA profile: ${ctx?.slaName || 'No SLA'} · ${ctx?.articleCount ?? 0} related articles`)}</span>
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
              {data.suggestedActions.map((s) => (
                <SuggestionCard key={s.id} suggestion={s} onApply={handleApplySuggestion} />
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
              {actionFeedback && (
                <div
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border transition-all',
                    actionFeedback.type === 'success'
                      ? 'bg-success/10 text-success border-success/20'
                      : 'bg-destructive/10 text-destructive border-destructive/20',
                  )}
                >
                  {actionFeedback.type === 'success' ? (
                    <Check className="h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <X className="h-3.5 w-3.5 shrink-0" />
                  )}
                  <span className="flex-1">{actionFeedback.message}</span>
                </div>
              )}

              <button
                onClick={handleReclassification}
                disabled={actionLoading}
                className={cn(
                  'w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border transition-colors cursor-pointer',
                  actionLoading
                    ? 'border-border/30 text-muted-foreground/60 pointer-events-none'
                    : 'border-border/50 hover:border-border hover:bg-muted/50',
                )}
              >
                {actionLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-chart-1" />
                ) : (
                  <PenSquare className="h-4 w-4 text-chart-1" />
                )}
                {t('copilot.reclassify')}
              </button>
              <button
                onClick={handleEscalate}
                disabled={actionLoading}
                className={cn(
                  'w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border transition-colors cursor-pointer',
                  actionLoading
                    ? 'border-border/30 text-muted-foreground/60 pointer-events-none'
                    : 'border-border/50 hover:border-border hover:bg-muted/50',
                )}
              >
                {actionLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin text-warning" />
                ) : (
                  <ArrowUpRight className="h-4 w-4 text-warning" />
                )}
                {t('copilot.escalate')}
              </button>

              {!showNoteInput ? (
                <button
                  onClick={() => setShowNoteInput(true)}
                  disabled={actionLoading}
                  className={cn(
                    'w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border transition-colors cursor-pointer',
                    actionLoading
                      ? 'border-border/30 text-muted-foreground/60 pointer-events-none'
                      : 'border-border/50 hover:border-border hover:bg-muted/50',
                  )}
                >
                  {actionLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  ) : (
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  )}
                  {t('copilot.addNote')}
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Write a note..."
                    className="flex-1 text-sm bg-muted/50 border border-border/50 rounded-lg px-3 py-2 placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !actionLoading) handleAddNote()
                      if (e.key === 'Escape') { setShowNoteInput(false); setNewNote('') }
                    }}
                  />
                  <button
                    onClick={handleAddNote}
                    disabled={actionLoading || !newNote.trim()}
                    className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer"
                  >
                    {actionLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </div>
              )}
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
                <span className="text-foreground">{data.conversation.length} {t('copilot.messages')}</span>
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

