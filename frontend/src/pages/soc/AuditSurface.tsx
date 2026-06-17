/**
 * AuditSurface — immutable audit event log.
 *
 * Chronological timeline of audit events with actor, action type,
 * target, and expandable details.  Supports filtering by actor,
 * action type, and date range.
 */

import { useState, useMemo, useCallback } from 'react'
import { motion } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeAudit } from '../../services/soc/normalize/audit'
import { MOCK_AUDIT } from '../../services/soc/mockData'
import { SocEmptyState } from '../../components/soc'
import { applyNeutralCopy } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  ScrollText,
  Search,
  X,
  RefreshCw,
  SearchX,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.AUDIT

const PAGE_SIZE = 50

// ─── Types for supplementary audit data ──────────────────────────────────

interface MockAuditEvent {
  id: string
  actor: string
  action: string
  target: string
  timestamp: string
  details?: Record<string, unknown>
}

const MOCK_EVENTS: MockAuditEvent[] = [
  { id: 'evt-001', actor: 'Ana López', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-17T09:15:00Z', details: { ip: '10.0.1.42', browser: 'Chrome 125', session: 'abc123' } },
  { id: 'evt-002', actor: 'Carlos Ruiz', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-17T09:12:00Z', details: { ip: '10.0.1.55', browser: 'Firefox 127', session: 'def456' } },
  { id: 'evt-003', actor: 'Ana López', action: 'TicketAction', target: 'TKT-1024 — Circuit timeout on MX-480', timestamp: '2026-06-17T09:10:00Z', details: { action: 'status_change', from: 'open', to: 'in_progress' } },
  { id: 'evt-004', actor: 'Miguel Torres', action: 'TicketAction', target: 'TKT-1021 — BGP flap recurrence', timestamp: '2026-06-17T08:55:00Z', details: { action: 'note_added', note: 'Checking peer AS64512 config' } },
  { id: 'evt-005', actor: 'Pedro Martínez', action: 'ConfigChange', target: 'SLA Warning Threshold', timestamp: '2026-06-17T08:30:00Z', details: { setting: 'sla_warning_pct', old_value: '75', new_value: '80' } },
  { id: 'evt-006', actor: 'Laura García', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-17T08:20:00Z', details: { ip: '10.0.1.38', browser: 'Chrome 125', session: 'ghi789' } },
  { id: 'evt-007', actor: 'Carlos Ruiz', action: 'Escalation', target: 'TKT-1027 — DDoS mitigation (Lvl 2)', timestamp: '2026-06-17T08:15:00Z', details: { level: 2, reason: 'SLA breach imminent', assigned_to: 'Tier-3 NOC' } },
  { id: 'evt-008', actor: 'Sofía Ramírez', action: 'TicketAction', target: 'TKT-1015 — SSL certificate renewal', timestamp: '2026-06-17T07:50:00Z', details: { action: 'resolution', resolution: 'Certificate reissued via ACME' } },
  { id: 'evt-009', actor: 'Diego Fernández', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-17T07:45:00Z', details: { ip: '10.0.1.72', browser: 'Edge 125', session: 'jkl012' } },
  { id: 'evt-010', actor: 'Valentina Ortiz', action: 'TicketAction', target: 'TKT-1018 — Port security violation', timestamp: '2026-06-17T07:30:00Z', details: { action: 'assignment', assigned_to: 'Security Team' } },
  { id: 'evt-011', actor: 'Pedro Martínez', action: 'ConfigChange', target: 'Escalation Timeout', timestamp: '2026-06-16T18:00:00Z', details: { setting: 'escalation_timeout_min', old_value: '30', new_value: '45' } },
  { id: 'evt-012', actor: 'Ana López', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-16T17:55:00Z', details: { ip: '10.0.1.42', browser: 'Chrome 125', session: 'mno345' } },
  { id: 'evt-013', actor: 'Miguel Torres', action: 'Escalation', target: 'TKT-1021 — BGP flap (Lvl 1)', timestamp: '2026-06-16T17:30:00Z', details: { level: 1, reason: 'Unresolved after 2h', assigned_to: 'Senior Engineer' } },
  { id: 'evt-014', actor: 'Carlos Ruiz', action: 'TicketAction', target: 'TKT-1027 — DDoS mitigation', timestamp: '2026-06-16T17:15:00Z', details: { action: 'status_change', from: 'open', to: 'in_progress' } },
  { id: 'evt-015', actor: 'Sofía Ramírez', action: 'Login', target: 'SOC Shell', timestamp: '2026-06-16T17:00:00Z', details: { ip: '10.0.1.30', browser: 'Chrome 125', session: 'pqr678' } },
]

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return formatTimestamp(iso)
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Maps actor name to a dot colour: human → blue, system → green, IA → purple. */
function getActorDotColor(actor: string): string {
  const lower = actor.toLowerCase()
  if (lower === 'system') return 'bg-emerald-500'
  if (lower.includes('ia') || lower.includes('bot') || lower.startsWith('ai ')) return 'bg-purple-500'
  return 'bg-blue-500'
}

/** Maps action type to a pill badge colour. */
function getActionPillColor(action: string): string {
  const lower = action.toLowerCase()
  if (lower.includes('login')) return 'bg-chart-2/10 text-chart-2 border-chart-2/20'
  if (lower.includes('ticket') || lower.includes('note')) return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
  if (lower.includes('config') || lower.includes('setting')) return 'bg-warning/10 text-warning border-warning/20'
  if (lower.includes('escalat') || lower.includes('breach')) return 'bg-destructive/10 text-destructive border-destructive/20'
  if (lower.includes('agent') || lower.includes('kb') || lower.includes('article')) return 'bg-sky-500/10 text-sky-500 border-sky-500/20'
  return 'bg-muted text-muted-foreground border-border/50'
}

/** Converts a PascalCase action name to kebab-case dot notation. */
function formatActionName(action: string): string {
  // Already in dot notation (e.g. ticket.updated) — keep as-is
  if (action.includes('.')) return action
  // PascalCase → kebab-case dots (e.g. TicketAction → ticket.action)
  return action
    .replace(/([A-Z])/g, '.$1')
    .toLowerCase()
    .replace(/^\./, '')
}

/** Derives a resource_type:resource_id label from the event. */
function formatTarget(event: MockAuditEvent): string {
  const { target, action } = event
  const lower = action.toLowerCase()
  if (lower.includes('login')) return `session:${target}`
  if (lower.includes('ticket')) {
    const idMatch = target.match(/(TKT-\d+)/)
    if (idMatch) return `ticket:${idMatch[1]}`
  }
  if (lower.includes('config') || lower.includes('setting')) return `config:${target}`
  if (lower.includes('escalat')) {
    const idMatch = target.match(/(TKT-\d+)/)
    if (idMatch) return `ticket:${idMatch[1]}`
    return `escalation:${target}`
  }
  return target
}

/** Returns the first string value from details as a brief description. */
function getBriefDescription(details?: Record<string, unknown>): string {
  if (!details || Object.keys(details).length === 0) return ''
  const firstStr = Object.values(details).find((v): v is string => typeof v === 'string')
  return firstStr || ''
}

// ─── Animation variants ──────────────────────────────────────────────────

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.04 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' as const } },
}

// ─── Loading skeleton ─────────────────────────────────────────────────────

function AuditSkeleton() {
  return (
    <div className="divide-y divide-border/20">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="flex items-start gap-4 px-4 py-3.5 animate-pulse"
        >
          {/* Dot column */}
          <div className="flex flex-col items-center gap-1 shrink-0 pt-0.5">
            <div className="h-3 w-3 rounded-full bg-muted-foreground/20" />
            <div className="w-px h-full min-h-[20px] bg-border/20" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-3 w-24 rounded bg-muted-foreground/20" />
              <div className="h-3 w-16 rounded bg-muted-foreground/20" />
              <div className="h-3 w-12 rounded bg-muted-foreground/20" />
            </div>
            <div className="h-2.5 w-3/5 rounded bg-muted-foreground/15" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────

function AuditEventRow({ event }: { event: MockAuditEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = event.details && Object.keys(event.details).length > 0
  const desc = getBriefDescription(event.details)
  const titleIso = formatTimestamp(event.timestamp)

  return (
    <motion.div variants={itemVariants}>
      <div className="border-b border-border/30 last:border-b-0 hover:bg-muted/30 transition-colors">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-start gap-4 px-4 py-3.5 text-left cursor-pointer"
        >
          {/* Colour-coded dot + vertical line */}
          <div className="flex flex-col items-center gap-1 shrink-0 pt-0.5">
            <div
              className={cn(
                'rounded-full h-3 w-3 ring-2 ring-background',
                getActorDotColor(event.actor),
              )}
            />
            <div className="w-px h-full min-h-[20px] bg-border/30" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Row 1: actor · action pill · relative time · target */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs font-medium text-foreground">{event.actor}</span>

              <span
                className={cn(
                  'text-[10px] font-medium px-1.5 py-0.5 rounded border',
                  getActionPillColor(event.action),
                )}
              >
                {formatActionName(event.action)}
              </span>

              <span className="text-[10px] text-muted-foreground" title={titleIso}>
                {formatRelativeTime(event.timestamp)}
              </span>

              <span className="text-[10px] text-muted-foreground/60 font-mono">
                {formatTarget(event)}
              </span>
            </div>

            {/* Row 2: brief description or target fallback (truncated) */}
            {desc ? (
              <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-2xl">
                {desc}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-2xl">
                {applyNeutralCopy(event.target)}
              </p>
            )}
          </div>

          {/* Expand indicator */}
          {hasDetails && (
            <div className="shrink-0 text-muted-foreground self-start pt-1">
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </div>
          )}
        </button>

        {/* Expanded details */}
        {expanded && hasDetails && event.details && (
          <div className="px-4 pb-3 pl-[60px]">
            <div className="text-[10px] text-muted-foreground bg-muted/50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono">
              <pre className="m-0">{JSON.stringify(event.details, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function AuditSurface() {
  const { data, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.AUDIT],
    normalizeAudit,
    MOCK_AUDIT,
    SURFACE_ID,
  )

  // ── UI state ──
  const [actorFilter, setActorFilter] = useState('')
  const [actionTextFilter, setActionTextFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [page, setPage] = useState(1)
  const [lastUpdated] = useState(() => new Date().toISOString())
  const [events] = useState<MockAuditEvent[]>(MOCK_EVENTS)

  // ── Actor options (from normalized data.actors + supplementary events) ──
  const actorOptions = useMemo(() => {
    const fromData = data?.actors ?? []
    const fromEvents = [...new Set(events.map((e) => e.actor))]
    const combined = new Set([...fromData, ...fromEvents])
    return [...combined].sort()
  }, [data?.actors, events])

  // ── Derived ──
  const filteredEvents = useMemo(() => {
    let result = events

    if (actorFilter) {
      result = result.filter((e) => e.actor === actorFilter)
    }

    if (actionTextFilter.trim()) {
      const q = actionTextFilter.toLowerCase()
      result = result.filter((e) => e.action.toLowerCase().includes(q))
    }

    if (startDate) {
      const start = new Date(startDate)
      start.setHours(0, 0, 0, 0)
      result = result.filter((e) => new Date(e.timestamp) >= start)
    }

    if (endDate) {
      const end = new Date(endDate)
      end.setHours(23, 59, 59, 999)
      result = result.filter((e) => new Date(e.timestamp) <= end)
    }

    return result
  }, [events, actorFilter, actionTextFilter, startDate, endDate])

  const totalFiltered = filteredEvents.length
  const totalPages = Math.max(1, Math.ceil(totalFiltered / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const paginatedEvents = filteredEvents.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  )
  const activeFilterCount = [actorFilter, actionTextFilter, startDate, endDate].filter(Boolean).length
  const hasActiveFilters = activeFilterCount > 0

  // When filters reduce results below current page, clamp page
  const safePageNum = Math.min(page, totalPages)

  const clearFilters = useCallback(() => {
    setActorFilter('')
    setActionTextFilter('')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }, [])

  const handleRefresh = useCallback(() => {
    setPage(1)
    refresh()
  }, [refresh])

  const isDemo = source === 'mock'

  // ── Loading ──
  if (loading) {
    return (
      <div className="space-y-4">
        {/* Header skeleton */}
        <div className="flex items-center gap-2">
          <ScrollText className="h-5 w-5 text-chart-3" />
          <h2 className="text-lg font-semibold">surfaces.audit</h2>
        </div>

        {/* Skeleton list */}
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <AuditSkeleton />
        </div>
      </div>
    )
  }

  // ── Empty (only when source is backend and data is truly empty) ──
  if (source === 'backend' && data.events.length === 0 && events.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <div className="space-y-4">
      {/* ── Error fallback banner ── */}
      {source === 'error' && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Failed to load data from server. Showing cached/demo data.</span>
          </div>
          <button
            onClick={handleRefresh}
            className="underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </motion.div>
      )}

      {/* ── Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2"
      >
        <ScrollText className="h-5 w-5 text-chart-3" />
        <h2 className="text-lg font-semibold">Audit Trail</h2>
        <span className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-chart-3/10 text-chart-3 text-[10px] font-medium leading-none">
          {totalFiltered}
        </span>

        {/* Refresh button + last updated */}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground/60 hidden sm:inline">
            Updated {formatRelativeTime(lastUpdated)}
          </span>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
            title="Refresh audit trail"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        {isDemo && (
          <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            Demo
          </div>
        )}
      </motion.div>

      {/* ── Filter bar ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        className="bg-card rounded-2xl border border-border/50 shadow-sm p-4"
      >
        <div className="flex flex-wrap items-center gap-3">
          {/* Actor dropdown */}
          <select
            value={actorFilter}
            onChange={(e) => { setActorFilter(e.target.value); setPage(1) }}
            className="flex-1 min-w-[120px] max-w-[170px] px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-ring appearance-none cursor-pointer"
          >
            <option value="">Actor</option>
            {actorOptions.map((actor) => (
              <option key={actor} value={actor}>
                {actor}
              </option>
            ))}
          </select>

          {/* Action text filter */}
          <div className="relative flex-1 min-w-[120px] max-w-[170px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <input
              type="text"
              value={actionTextFilter}
              onChange={(e) => { setActionTextFilter(e.target.value); setPage(1) }}
              placeholder="Action..."
              className={cn(
                'w-full pl-8 pr-7 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
                'placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring',
              )}
            />
            {actionTextFilter && (
              <button
                onClick={() => { setActionTextFilter(''); setPage(1) }}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Date from */}
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setPage(1) }}
            className="flex-1 min-w-[100px] max-w-[150px] px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            title="From date"
          />

          {/* Date to */}
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setPage(1) }}
            className="flex-1 min-w-[100px] max-w-[150px] px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            title="To date"
          />

          {/* Active filter count + clear */}
          {hasActiveFilters && (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-primary/10 text-primary text-[10px] font-medium leading-none">
                {activeFilterCount}
              </span>
              <button
                onClick={clearFilters}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="h-3 w-3" />
                Clear
              </button>
            </div>
          )}
        </div>
      </motion.div>

      {/* ── Timeline / feed ── */}
      {paginatedEvents.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm"
        >
          <SearchX className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">No audit events found</p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="mt-3 text-xs text-primary hover:underline cursor-pointer"
            >
              Clear filters
            </button>
          )}
        </motion.div>
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden"
        >
          <div className="divide-y divide-border/20">
            {paginatedEvents.map((event) => (
              <AuditEventRow key={event.id} event={event} />
            ))}
          </div>
        </motion.div>
      )}

      {/* ── Pagination ── */}
      {totalFiltered > PAGE_SIZE && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.25 }}
          className="flex items-center justify-between px-4 py-2 text-xs text-muted-foreground bg-card rounded-xl border border-border/50 shadow-sm"
        >
          <span>
            Showing {(safePageNum - 1) * PAGE_SIZE + 1}–
            {Math.min(safePageNum * PAGE_SIZE, totalFiltered)} of {totalFiltered} events
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePageNum <= 1}
              className={cn(
                'flex items-center gap-1 px-2 py-1 rounded-md transition-colors cursor-pointer',
                safePageNum <= 1
                  ? 'text-muted-foreground/30 cursor-not-allowed'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
              )}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePageNum >= totalPages}
              className={cn(
                'flex items-center gap-1 px-2 py-1 rounded-md transition-colors cursor-pointer',
                safePageNum >= totalPages
                  ? 'text-muted-foreground/30 cursor-not-allowed'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
              )}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </div>
  )
}
