/**
 * SlaWarRoomSurface — SLA monitoring dashboard.
 *
 * Shows active SLA timers with countdown colour coding, breach alerts
 * with escalation status, and a priority × queue compliance matrix.
 */

import { useState, useEffect, useCallback } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { normalizeSlaWarRoom } from '../../services/soc/normalize/slaWarRoom'
import type { SlaWarRoomView } from '../../services/soc/normalize/slaWarRoom'
import { SocLoadingState, SocEmptyState, SocErrorState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  AlertTriangle,
  Clock,
  AlertOctagon,
  ArrowUpRight,
  Shield,
  Gauge,
  Timer,
  BarChart3,
  User,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.SLA_WAR_ROOM

const PRIORITY_MATRIX_ROWS = ['critical', 'high', 'medium', 'low'] as const
const PRIORITY_MATRIX_LABELS: Record<string, string> = {
  critical: t('ticket.priority.critical'),
  high: t('ticket.priority.high'),
  medium: t('ticket.priority.medium'),
  low: t('ticket.priority.low'),
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatTimeRemaining(seconds: number): string {
  if (seconds <= 0) return t('sla.breached')
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

function getTimerColorClass(remainingSeconds: number, totalSeconds: number): string {
  const pct = totalSeconds > 0 ? remainingSeconds / totalSeconds : 0
  if (remainingSeconds <= 0) return 'bg-destructive/10 border-destructive/30 text-destructive'
  if (pct < 0.25) return 'bg-destructive/5 border-destructive/20 text-destructive'
  if (pct < 0.5) return 'bg-warning/5 border-warning/20 text-warning'
  return 'bg-success/5 border-success/20 text-success'
}

function getTimerDotColor(remainingSeconds: number, totalSeconds: number): string {
  const pct = totalSeconds > 0 ? remainingSeconds / totalSeconds : 0
  if (remainingSeconds <= 0) return 'bg-destructive'
  if (pct < 0.25) return 'bg-destructive'
  if (pct < 0.5) return 'bg-warning'
  return 'bg-success'
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

// ─── Mock data ────────────────────────────────────────────────────────────

interface ActiveSlaTimer {
  ticketId: string
  subject: string
  priority: string
  deadline: string
  remainingSeconds: number
  totalSeconds: number
}

interface BreachAlert {
  id: string
  ticketId: string
  subject: string
  priority: string
  status: 'breached' | 'near-breach'
  timeSinceBreach: string
  escalationLevel: number
  assignedAgent: string
}

interface PriorityComplianceCell {
  priority: string
  queue: string
  compliance: number // 0–100
  total: number
  breached: number
}

const QUEUES = ['Network', 'Security', 'Applications', 'Infrastructure']

const MOCK_TIMERS: ActiveSlaTimer[] = [
  { ticketId: 'TKT-1024', subject: 'Circuit timeout on MX-480 edge router', priority: 'critical', deadline: '2026-06-17T18:00:00Z', remainingSeconds: 1800, totalSeconds: 3600 },
  { ticketId: 'TKT-1021', subject: 'BGP flap recurrence — Tier-1 ISP peer', priority: 'high', deadline: '2026-06-17T20:00:00Z', remainingSeconds: 5400, totalSeconds: 14400 },
  { ticketId: 'TKT-1018', subject: 'Port security violation — access switch', priority: 'medium', deadline: '2026-06-18T06:00:00Z', remainingSeconds: 28800, totalSeconds: 28800 },
  { ticketId: 'TKT-1015', subject: 'SSL certificate renewal — *.fedeto.com', priority: 'low', deadline: '2026-06-19T12:00:00Z', remainingSeconds: 72000, totalSeconds: 86400 },
  { ticketId: 'TKT-1027', subject: 'DDoS mitigation rule deployment', priority: 'critical', deadline: '2026-06-17T16:30:00Z', remainingSeconds: -600, totalSeconds: 3600 },
]

const MOCK_BREACHES: BreachAlert[] = [
  { id: 'br-1', ticketId: 'TKT-1027', subject: 'DDoS mitigation rule deployment', priority: 'critical', status: 'breached', timeSinceBreach: '12 min', escalationLevel: 2, assignedAgent: 'Carlos Ruiz' },
  { id: 'br-2', ticketId: 'TKT-1024', subject: 'Circuit timeout on MX-480 edge router', priority: 'critical', status: 'near-breach', timeSinceBreach: '—', escalationLevel: 1, assignedAgent: 'Ana López' },
  { id: 'br-3', ticketId: 'TKT-1021', subject: 'BGP flap recurrence — Tier-1 ISP peer', priority: 'high', status: 'near-breach', timeSinceBreach: '—', escalationLevel: 0, assignedAgent: 'Miguel Torres' },
]

const MOCK_MATRIX: PriorityComplianceCell[] = [
  { priority: 'critical', queue: 'Network', compliance: 78, total: 45, breached: 10 },
  { priority: 'critical', queue: 'Security', compliance: 92, total: 38, breached: 3 },
  { priority: 'critical', queue: 'Applications', compliance: 65, total: 20, breached: 7 },
  { priority: 'critical', queue: 'Infrastructure', compliance: 85, total: 32, breached: 5 },
  { priority: 'high', queue: 'Network', compliance: 82, total: 62, breached: 11 },
  { priority: 'high', queue: 'Security', compliance: 88, total: 55, breached: 7 },
  { priority: 'high', queue: 'Applications', compliance: 73, total: 40, breached: 11 },
  { priority: 'high', queue: 'Infrastructure', compliance: 90, total: 48, breached: 5 },
  { priority: 'medium', queue: 'Network', compliance: 91, total: 80, breached: 7 },
  { priority: 'medium', queue: 'Security', compliance: 95, total: 72, breached: 4 },
  { priority: 'medium', queue: 'Applications', compliance: 87, total: 65, breached: 8 },
  { priority: 'medium', queue: 'Infrastructure', compliance: 93, total: 70, breached: 5 },
  { priority: 'low', queue: 'Network', compliance: 97, total: 120, breached: 4 },
  { priority: 'low', queue: 'Security', compliance: 99, total: 98, breached: 1 },
  { priority: 'low', queue: 'Applications', compliance: 96, total: 110, breached: 4 },
  { priority: 'low', queue: 'Infrastructure', compliance: 98, total: 105, breached: 2 },
]

// ─── Sub-components ───────────────────────────────────────────────────────

function TimerCard({ timer }: { timer: ActiveSlaTimer }) {
  const isBreached = timer.remainingSeconds <= 0
  const pct = timer.totalSeconds > 0 ? (timer.remainingSeconds / timer.totalSeconds) * 100 : 0
  const colorClass = getTimerColorClass(timer.remainingSeconds, timer.totalSeconds)

  return (
    <div className={cn('relative group bg-card rounded-2xl p-4 border shadow-sm transition-all duration-300 hover:shadow-md', colorClass)}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn('w-2 h-2 rounded-full', getTimerDotColor(timer.remainingSeconds, timer.totalSeconds))} />
          <span className="font-mono text-xs font-medium">{timer.ticketId}</span>
        </div>
        <span className={cn('text-[10px] font-medium px-2 py-0.5 rounded border', priorityBadgeClass(timer.priority))}>
          {t(`ticket.priority.${timer.priority}`)}
        </span>
      </div>
      <p className="text-sm text-foreground truncate mb-3">{timer.subject}</p>
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-muted-foreground">
          <Timer className="h-3 w-3" />
          <span>{isBreached ? t('sla.breached') : formatTimeRemaining(timer.remainingSeconds)}</span>
        </div>
        <span className={cn('font-semibold', isBreached ? 'text-destructive' : pct < 25 ? 'text-destructive' : pct < 50 ? 'text-warning' : 'text-success')}>
          {Math.max(0, Math.round(pct))}%
        </span>
      </div>
      {/* Progress bar */}
      <div className="mt-2 h-1.5 w-full bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isBreached ? 'bg-destructive' : pct < 25 ? 'bg-destructive' : pct < 50 ? 'bg-warning' : 'bg-success',
          )}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  )
}

function BreachRow({ breach }: { breach: BreachAlert }) {
  return (
    <div className={cn(
      'flex items-center gap-4 px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors text-sm',
      breach.status === 'breached' && 'bg-destructive/5',
    )}>
      <div className={cn(
        'rounded-full p-1 shrink-0',
        breach.status === 'breached' ? 'bg-destructive/10 text-destructive' : 'bg-warning/10 text-warning',
      )}>
        {breach.status === 'breached' ? (
          <AlertOctagon className="h-3.5 w-3.5" />
        ) : (
          <AlertTriangle className="h-3.5 w-3.5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-medium">{breach.ticketId}</span>
          <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded border', priorityBadgeClass(breach.priority))}>
            {t(`ticket.priority.${breach.priority}`)}
          </span>
          {breach.escalationLevel > 0 && (
            <span className="text-[10px] font-medium text-warning flex items-center gap-0.5">
              <ArrowUpRight className="h-3 w-3" />
              Lvl {breach.escalationLevel}
            </span>
          )}
        </div>
        <p className="text-xs text-muted-foreground truncate mt-0.5">{breach.subject}</p>
      </div>
      <div className="text-right shrink-0">
        <p className={cn(
          'text-xs font-medium',
          breach.status === 'breached' ? 'text-destructive' : 'text-warning',
        )}>
          {breach.status === 'breached' ? breach.timeSinceBreach : t('sla.nearBreach')}
        </p>
        <p className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5 justify-end">
          <User className="h-3 w-3" />
          {breach.assignedAgent}
        </p>
      </div>
    </div>
  )
}

function ComplianceCell({ cell }: { cell: PriorityComplianceCell }) {
  const colorClass = cell.compliance >= 90
    ? 'bg-success/10 text-success'
    : cell.compliance >= 75
      ? 'bg-warning/10 text-warning'
      : 'bg-destructive/10 text-destructive'

  return (
    <div className={cn('rounded-xl p-3 text-center border border-border/30', colorClass)}>
      <p className="text-lg font-bold">{cell.compliance}%</p>
      <p className="text-[10px] text-muted-foreground mt-0.5">
        {cell.total} tickets · {cell.breached} {t('sla.breached').toLowerCase()}
      </p>
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function SlaWarRoomSurface() {
  const { setSurfaceStatus } = useSocShell()
  const [data, setData] = useState<SlaWarRoomView | null>(null)
  const [error, setError] = useState<SocError | null>(null)
  const [loading, setLoading] = useState(true)

  // Richer UI data from mock fallback
  const [timers] = useState<ActiveSlaTimer[]>(MOCK_TIMERS)
  const [breaches] = useState<BreachAlert[]>(MOCK_BREACHES)
  const [matrix] = useState<PriorityComplianceCell[]>(MOCK_MATRIX)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSurfaceStatus(SURFACE_ID, 'loading')

    try {
      const raw = await socFetch<Record<string, unknown>>(SOC_ENDPOINTS[SURFACE_ID])
      const view = normalizeSlaWarRoom(raw)
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

  // ── Loading ──

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.slaWarRoom')} />
  }

  // ── Error ──

  if (error) {
    return <SocErrorState error={error} />
  }

  // ── Empty ──

  if (!data || (data.breachTimers.length === 0 && data.activeSLAs.length === 0)) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-2">
        <Gauge className="h-5 w-5 text-chart-1" />
        <h2 className="text-lg font-semibold">{t('surfaces.slaWarRoom')}</h2>
      </div>

      {/* Active SLA Timers */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Clock className="h-4 w-4 text-chart-2" />
          <h3 className="text-sm font-semibold">{t('sla.activeTimers')}</h3>
          <span className="ml-auto text-xs text-muted-foreground">
            {timers.length} {t('sla.active')}
          </span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {timers.map((timer) => (
            <TimerCard key={timer.ticketId} timer={timer} />
          ))}
        </div>
      </div>

      {/* Breach Alerts + Priority Matrix side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Breach Alerts */}
        <div className="lg:col-span-3 bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <AlertOctagon className="h-4 w-4 text-destructive" />
            <h3 className="text-sm font-semibold">{t('sla.breachAlerts')}</h3>
            <span className="ml-auto text-xs text-muted-foreground">
              {breaches.filter((b) => b.status === 'breached').length} {t('sla.breached').toLowerCase()} · {breaches.length} {t('sla.alerts')}
            </span>
          </div>
          <div className="divide-y divide-border/30">
            {breaches.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
                <p className="text-xs">{t('empty.slaWarRoom')}</p>
              </div>
            ) : (
              breaches.map((breach) => (
                <BreachRow key={breach.id} breach={breach} />
              ))
            )}
          </div>
        </div>

        {/* Priority Matrix */}
        <div className="lg:col-span-2 bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <BarChart3 className="h-4 w-4 text-chart-3" />
            <h3 className="text-sm font-semibold">{t('sla.priorityMatrix')}</h3>
          </div>
          <div className="p-4 space-y-3">
            {/* Header row */}
            <div className="grid grid-cols-4 gap-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider text-center">
              <div />
              {QUEUES.map((q) => (
                <span key={q}>{q}</span>
              ))}
            </div>
            {/* Data rows */}
            {PRIORITY_MATRIX_ROWS.map((priority) => (
              <div key={priority} className="grid grid-cols-4 gap-2 items-center">
                <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', priorityBadgeClass(priority))}>
                  {PRIORITY_MATRIX_LABELS[priority]}
                </span>
                {QUEUES.map((queue) => {
                  const cell = matrix.find((m) => m.priority === priority && m.queue === queue)
                  return cell ? (
                    <ComplianceCell key={`${priority}-${queue}`} cell={cell} />
                  ) : (
                    <div key={`${priority}-${queue}`} className="rounded-xl p-3 bg-muted/30 text-center text-[10px] text-muted-foreground">
                      —
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
