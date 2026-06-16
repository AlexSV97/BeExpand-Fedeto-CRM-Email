/**
 * AuditSurface — immutable audit event log.
 *
 * Chronological timeline of audit events with actor, action type,
 * target, and expandable details.  Supports filtering by actor,
 * action type, and date range.
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { normalizeAudit } from '../../services/soc/normalize/audit'
import type { AuditView } from '../../services/soc/normalize/audit'
import { SocLoadingState, SocEmptyState, SocErrorState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  ScrollText,
  Search,
  Filter,
  X,
  LogIn,
  Ticket,
  Settings,
  ArrowUpRight,
  Shield,
  ChevronDown,
  ChevronUp,
  Calendar,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.AUDIT

const ACTION_TYPES = [
  { key: '', label: t('audit.allActions') },
  { key: 'Login', label: t('audit.actionLogin'), icon: LogIn },
  { key: 'TicketAction', label: t('audit.actionTicket'), icon: Ticket },
  { key: 'ConfigChange', label: t('audit.actionConfig'), icon: Settings },
  { key: 'Escalation', label: t('audit.actionEscalation'), icon: ArrowUpRight },
] as const

const ACTION_ICONS: Record<string, typeof LogIn> = {
  Login: LogIn,
  TicketAction: Ticket,
  ConfigChange: Settings,
  Escalation: ArrowUpRight,
}

// ─── Mock data ────────────────────────────────────────────────────────────

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

function actionColor(action: string): string {
  switch (action) {
    case 'Login':
      return 'bg-chart-2/10 text-chart-2 border-chart-2/20'
    case 'TicketAction':
      return 'bg-chart-1/10 text-chart-1 border-chart-1/20'
    case 'ConfigChange':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'Escalation':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    default:
      return 'bg-muted text-muted-foreground border-border/50'
  }
}

function actionIcon(action: string) {
  const Icon = ACTION_ICONS[action] ?? Shield
  return <Icon className="h-3.5 w-3.5" />
}

function formatDetails(details?: Record<string, unknown>): string {
  if (!details || Object.keys(details).length === 0) return ''
  return Object.entries(details)
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n')
}

// ─── Sub-components ───────────────────────────────────────────────────────

function AuditEventRow({ event }: { event: MockAuditEvent }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = event.details && Object.keys(event.details).length > 0

  return (
    <div className="border-b border-border/30 last:border-b-0 hover:bg-muted/30 transition-colors">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-4 px-4 py-3.5 text-left cursor-pointer"
      >
        {/* Timeline dot */}
        <div className="flex flex-col items-center gap-1 shrink-0 pt-0.5">
          <div className={cn('rounded-full p-1.5', actionColor(event.action))}>
            {actionIcon(event.action)}
          </div>
          <div className="w-px h-full min-h-[20px] bg-border/30" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-foreground">{event.actor}</span>
            <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded border', actionColor(event.action))}>
              {t(`audit.action${event.action}`)}
            </span>
            <span className="text-[10px] text-muted-foreground">{formatTimestamp(event.timestamp)}</span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{event.target}</p>
        </div>

        {hasDetails && (
          <div className="shrink-0 text-muted-foreground">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        )}
      </button>

      {/* Expandable details */}
      {expanded && hasDetails && event.details && (
        <div className="px-4 pb-3 pl-[60px]">
          <pre className="text-[10px] text-muted-foreground bg-muted/50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono">
            {formatDetails(event.details)}
          </pre>
        </div>
      )}
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function AuditSurface() {
  const { setSurfaceStatus } = useSocShell()
  const [data, setData] = useState<AuditView | null>(null)
  const [error, setError] = useState<SocError | null>(null)
  const [loading, setLoading] = useState(true)

  // UI state
  const [actorSearch, setActorSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [events] = useState<MockAuditEvent[]>(MOCK_EVENTS)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSurfaceStatus(SURFACE_ID, 'loading')

    try {
      const raw = await socFetch<Record<string, unknown>>(SOC_ENDPOINTS[SURFACE_ID])
      const view = normalizeAudit(raw)
      setData(view)
      setSurfaceStatus(SURFACE_ID, 'ready')
    } catch (err: unknown) {
      const socErr: SocError = {
        code: err instanceof Error && 'code' in err ? (err as { code: string }).code : 'UNKNOWN_ERROR',
        message: err instanceof Error ? err.message : String(err),
        retry: fetchData,
      }
      setError(socErr)
      setSurfaceStatus(SURFACE_ID, 'error')
    } finally {
      setLoading(false)
    }
  }, [setSurfaceStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ── Derived ──

  const filteredEvents = useMemo(() => {
    let result = events

    if (actorSearch.trim()) {
      const q = actorSearch.toLowerCase()
      result = result.filter((e) => e.actor.toLowerCase().includes(q))
    }

    if (actionFilter) {
      result = result.filter((e) => e.action === actionFilter)
    }

    if (startDate) {
      const start = new Date(startDate)
      result = result.filter((e) => new Date(e.timestamp) >= start)
    }

    if (endDate) {
      const end = new Date(endDate)
      end.setHours(23, 59, 59, 999)
      result = result.filter((e) => new Date(e.timestamp) <= end)
    }

    return result
  }, [events, actorSearch, actionFilter, startDate, endDate])

  const hasActiveFilters = actorSearch || actionFilter || startDate || endDate

  const clearFilters = () => {
    setActorSearch('')
    setActionFilter('')
    setStartDate('')
    setEndDate('')
  }

  // ── Loading ──

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.audit')} />
  }

  // ── Error ──

  if (error) {
    return <SocErrorState error={error} />
  }

  // ── Empty ──

  if (!data || (data.events.length === 0 && events.length === 0)) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <ScrollText className="h-5 w-5 text-chart-3" />
        <h2 className="text-lg font-semibold">{t('surfaces.audit')}</h2>
        <span className="text-xs text-muted-foreground">
          ({events.length} {t('audit.events')})
        </span>
      </div>

      {/* Filters bar */}
      <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Actor search */}
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              value={actorSearch}
              onChange={(e) => setActorSearch(e.target.value)}
              placeholder={t('audit.searchActor')}
              className={cn(
                'w-full pl-9 pr-8 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
                'placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring',
              )}
            />
            {actorSearch && (
              <button
                onClick={() => setActorSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Action type dropdown */}
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className={cn(
              'px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
              'text-foreground focus:outline-none focus:ring-1 focus:ring-ring',
            )}
          >
            {ACTION_TYPES.map((at) => (
              <option key={at.key} value={at.key}>
                {at.label}
              </option>
            ))}
          </select>

          {/* Date range */}
          <div className="flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={cn(
                'px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
                'text-foreground focus:outline-none focus:ring-1 focus:ring-ring',
              )}
              placeholder={t('audit.fromDate')}
            />
            <span className="text-[10px] text-muted-foreground">{t('audit.to')}</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className={cn(
                'px-3 py-2 text-sm bg-muted/50 border border-border/50 rounded-lg',
                'text-foreground focus:outline-none focus:ring-1 focus:ring-ring',
              )}
              placeholder={t('audit.toDate')}
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              <Filter className="h-3 w-3" />
              {t('audit.clearFilters')}
            </button>
          )}
        </div>
      </div>

      {/* Timeline */}
      {filteredEvents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm">
          <ScrollText className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">{t('empty.audit')}</p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="mt-3 text-xs text-primary hover:underline cursor-pointer"
            >
              {t('audit.clearFilters')}
            </button>
          )}
        </div>
      ) : (
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="divide-y divide-border/20">
            {filteredEvents.map((event) => (
              <AuditEventRow key={event.id} event={event} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
