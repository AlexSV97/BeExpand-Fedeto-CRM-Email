/**
 * SlaWarRoomSurface — SLA monitoring dashboard.
 *
 * Shows active SLA timers with countdown colour coding, breach alerts
 * with escalation status, and a priority × queue compliance matrix.
 */

import { useState } from 'react'
import { SURFACE_IDS } from '../../services/soc/contracts'

import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeSlaWarRoom } from '../../services/soc/normalize/slaWarRoom'
import {
  MOCK_SLA_WAR_ROOM,
  MOCK_SLA_TIMERS,
  MOCK_SLA_BREACHES,
  MOCK_SLA_MATRIX,
  QUEUES,
} from '../../services/soc/mockData'
import type {
  ActiveSlaTimer,
  BreachAlert,
  PriorityComplianceCell,
} from '../../services/soc/mockData'
import { SocLoadingState, SocEmptyState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
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
      <p className="text-sm text-foreground truncate mb-3">{applyNeutralCopy(timer.subject)}</p>
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-1 text-muted-foreground">
          <Timer className="h-3 w-3" />
          <span>{isBreached ? t('sla.breached') : formatTimeRemaining(timer.remainingSeconds)}</span>
        </div>
        <span className={cn('font-semibold', isBreached ? 'text-destructive' : pct < 25 ? 'text-destructive' : pct < 50 ? 'text-warning' : 'text-success')}>
          {Math.max(0, Math.round(pct))}%
        </span>
      </div>
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
        <p className="text-xs text-muted-foreground truncate mt-0.5">{applyNeutralCopy(breach.subject)}</p>
      </div>
      <div className="text-right shrink-0">
        <p className={cn('text-xs font-medium', breach.status === 'breached' ? 'text-destructive' : 'text-warning')}>
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
  const { data, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.SLA_WAR_ROOM],
    normalizeSlaWarRoom,
    MOCK_SLA_WAR_ROOM,
    SURFACE_ID,
  )

  // Supplementary rich data (always from mock — no backend endpoint)
  const [timers] = useState<ActiveSlaTimer[]>(MOCK_SLA_TIMERS)
  const [breaches] = useState<BreachAlert[]>(MOCK_SLA_BREACHES)
  const [matrix] = useState<PriorityComplianceCell[]>(MOCK_SLA_MATRIX)

  // ── Loading ──
  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.slaWarRoom')} />
  }

  // ── Error ──
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Empty (only when source is backend and data is empty) ──
  if (source === 'backend' && data.breachTimers.length === 0 && data.activeSLAs.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  const isDemo = source === 'mock'

  // ── Content ──
  return (
    <div className="space-y-6">
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

      {/* Page header + demo badge */}
      <div className="flex items-center gap-2">
        <Gauge className="h-5 w-5 text-chart-1" />
        <h2 className="text-lg font-semibold">{t('surfaces.slaWarRoom')}</h2>
        {isDemo && (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            {"Demo"}
          </div>
        )}
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
            <div className="grid grid-cols-4 gap-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider text-center">
              <div />
              {QUEUES.map((q) => (
                <span key={q}>{q}</span>
              ))}
            </div>
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

