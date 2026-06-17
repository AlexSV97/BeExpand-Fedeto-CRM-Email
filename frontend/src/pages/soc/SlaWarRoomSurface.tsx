/**
 * SlaWarRoomSurface — Real-time SLA War Room monitoring dashboard.
 *
 * Professional real-time monitoring UI with:
 * - Header with status badges and refresh controls
 * - Three-column metric bar with SVG circular progress
 * - SLA Breach Timer rows sorted by urgency
 * - Escalations compact table
 * - Active SLA definition cards grid
 */

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeSlaWarRoom } from '../../services/soc/normalize/slaWarRoom'
import {
  MOCK_SLA_WAR_ROOM,
  MOCK_SLA_TIMERS,
  MOCK_SLA_BREACHES,
} from '../../services/soc/mockData'
import type { ActiveSlaTimer, BreachAlert } from '../../services/soc/mockData'
import { SocEmptyState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  AlertTriangle,
  Clock,
  AlertOctagon,
  ArrowUpRight,
  Shield,
  Timer,
  BarChart3,
  RefreshCw,
  Activity,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.SLA_WAR_ROOM

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatRemaining(seconds: number): string {
  if (seconds <= 0) return 'OVERDUE'
  const mins = Math.floor(seconds / 60)
  if (mins < 60) return `${mins}m left`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h left`
  const days = Math.floor(hours / 24)
  return `${days}d left`
}

function formatRelativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSec = Math.floor((now - then) / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

function formatSlaTarget(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function getTimerStatus(
  remainingSeconds: number,
  totalSeconds: number,
): 'breached' | 'warning' | 'ok' {
  if (remainingSeconds <= 0) return 'breached'
  const pct = totalSeconds > 0 ? remainingSeconds / totalSeconds : 0
  if (pct < 0.25) return 'warning'
  return 'ok'
}

function getTimerBorderColor(status: 'breached' | 'warning' | 'ok'): string {
  switch (status) {
    case 'breached':
      return 'border-l-destructive'
    case 'warning':
      return 'border-l-warning'
    case 'ok':
      return 'border-l-success'
  }
}

function getTimerBadgeColor(status: 'breached' | 'warning' | 'ok'): string {
  switch (status) {
    case 'breached':
      return 'bg-destructive/10 text-destructive border-destructive/20'
    case 'warning':
      return 'bg-warning/10 text-warning border-warning/20'
    case 'ok':
      return 'bg-success/10 text-success border-success/20'
  }
}

// ─── Skeleton Loading ────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-xl bg-muted', className)} />
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <Skeleton className="h-6 w-48" />
        <div className="ml-auto flex items-center gap-2">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
      </div>

      {/* Metric cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-32 rounded-2xl" />
        ))}
      </div>

      {/* List item skeletons */}
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

// ─── SVG Circular Progress ───────────────────────────────────────────────

function CircularProgress({
  value,
  size = 48,
  strokeWidth = 4,
}: {
  value: number
  size?: number
  strokeWidth?: number
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const clamped = Math.min(100, Math.max(0, value))
  const offset = circumference - (clamped / 100) * circumference

  return (
    <svg
      width={size}
      height={size}
      className="-rotate-90 shrink-0"
      viewBox={`0 0 ${size} ${size}`}
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        className="opacity-20"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-700 ease-out"
      />
    </svg>
  )
}

// ─── Sla Progress Bar ────────────────────────────────────────────────────

function SlaProgressBar({
  elapsed,
  total,
}: {
  elapsed: number
  total: number
}) {
  const pct = total > 0 ? Math.min(100, (elapsed / total) * 100) : 0
  const color =
    pct > 90
      ? 'bg-destructive'
      : pct > 60
        ? 'bg-warning'
        : 'bg-success'
  return (
    <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
      <div
        className={cn('h-full rounded-full transition-all duration-500', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ─── Metric Card ─────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string
  value: number
  sublabel: string
  color: 'success' | 'warning' | 'destructive'
  icon: React.ComponentType<{ className?: string }>
  delay: number
  circularValue: number
}

function MetricCard({
  label,
  value,
  sublabel,
  color,
  icon: Icon,
  delay,
  circularValue,
}: MetricCardProps) {
  const colorClasses = {
    success:
      'bg-success/5 border-success/20 text-success',
    warning:
      'bg-warning/5 border-warning/20 text-warning',
    destructive:
      'bg-destructive/5 border-destructive/20 text-destructive',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: 'easeOut' }}
      className={cn(
        'relative rounded-2xl p-5 border shadow-sm overflow-hidden bg-card',
        colorClasses[color],
      )}
    >
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Icon className="h-4 w-4" />
            <span className="text-sm font-medium">{label}</span>
          </div>
          <p className="text-3xl font-bold tabular-nums">{value}</p>
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        </div>
        <CircularProgress value={circularValue} size={56} strokeWidth={5} />
      </div>
    </motion.div>
  )
}

// ─── Breach Timer Row ────────────────────────────────────────────────────

function BreachTimerRow({
  timer,
  escalationLevel = 0,
  delay,
}: {
  timer: ActiveSlaTimer
  escalationLevel?: number
  delay: number
}) {
  const status = getTimerStatus(timer.remainingSeconds, timer.totalSeconds)
  const elapsed = timer.totalSeconds - timer.remainingSeconds

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.3, ease: 'easeOut' }}
      className={cn(
        'relative flex flex-col gap-2 px-5 py-4 border border-border/50 shadow-sm rounded-xl bg-card border-l-4 transition-all hover:shadow-md',
        getTimerBorderColor(status),
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={cn(
              'w-2 h-2 rounded-full shrink-0',
              status === 'breached'
                ? 'bg-destructive'
                : status === 'warning'
                  ? 'bg-warning'
                  : 'bg-success',
            )}
          />
          <span className="font-mono text-xs font-medium">
            {timer.ticketId}
          </span>
          <span className="text-sm text-foreground truncate">
            {applyNeutralCopy(timer.subject)}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Clock
            className={cn(
              'h-3.5 w-3.5',
              status === 'breached'
                ? 'text-destructive'
                : status === 'warning'
                  ? 'text-warning'
                  : 'text-success',
            )}
          />
          <span
            className={cn(
              'text-xs font-semibold tabular-nums',
              status === 'breached'
                ? 'text-destructive'
                : status === 'warning'
                  ? 'text-warning'
                  : 'text-success',
            )}
          >
            {formatRemaining(timer.remainingSeconds)}
          </span>
          <span
            className={cn(
              'text-[10px] font-medium px-1.5 py-0.5 rounded border',
              getTimerBadgeColor(status),
            )}
          >
            {status === 'breached'
              ? 'Breached'
              : status === 'warning'
                ? 'Warning'
                : 'OK'}
          </span>
          {escalationLevel > 0 && (
            <span className="text-[10px] font-medium text-warning flex items-center gap-0.5 bg-warning/5 px-1.5 py-0.5 rounded border border-warning/20">
              <ArrowUpRight className="h-3 w-3" />
              L{escalationLevel}
            </span>
          )}
        </div>
      </div>
      <SlaProgressBar elapsed={Math.max(0, elapsed)} total={timer.totalSeconds} />
    </motion.div>
  )
}

// ─── Escalation Row ──────────────────────────────────────────────────────

function getLevelBadge(level: number): { label: string; color: string } {
  const map: Record<number, { label: string; color: string }> = {
    1: {
      label: 'L1',
      color:
        'bg-chart-1/10 text-chart-1 border-chart-1/20',
    },
    2: {
      label: 'L2',
      color: 'bg-warning/10 text-warning border-warning/20',
    },
    3: {
      label: 'L3',
      color:
        'bg-destructive/10 text-destructive border-destructive/20',
    },
  }
  return (
    map[level] ?? {
      label: `L${level}`,
      color: 'bg-muted text-muted-foreground border-border/50',
    }
  )
}

function EscalationRow({
  ticketId,
  level,
  reason,
  escalatedAt,
  delay,
}: {
  ticketId: string
  level: number
  reason: string
  escalatedAt: string
  delay: number
}) {
  const badge = getLevelBadge(level)
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.25, ease: 'easeOut' }}
      className="flex items-center gap-4 px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors text-sm"
    >
      <span className="font-mono text-xs font-medium w-24 shrink-0">
        {ticketId}
      </span>
      <span
        className={cn(
          'text-[10px] font-medium px-1.5 py-0.5 rounded border shrink-0',
          badge.color,
        )}
      >
        {badge.label}
      </span>
      <span className="flex-1 text-xs text-muted-foreground truncate">
        {reason}
      </span>
      <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
        {formatRelativeTime(escalatedAt)}
      </span>
    </motion.div>
  )
}

// ─── SLA Definition Card ─────────────────────────────────────────────────

function SlaDefinitionCard({
  name,
  targetSeconds,
  activeCount,
  breachCount,
  delay,
}: {
  name: string
  targetSeconds: number
  activeCount: number
  breachCount: number
  delay: number
}) {
  const hasBreaches = breachCount > 0
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.3, ease: 'easeOut' }}
      className="bg-card rounded-2xl border border-border/50 shadow-sm p-4 hover:shadow-md transition-shadow"
    >
      <h4 className="text-sm font-semibold text-foreground mb-3">
        {name} SLA
      </h4>
      <div className="space-y-1.5 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Target</span>
          <span className="font-medium tabular-nums">
            {formatSlaTarget(targetSeconds)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Active</span>
          <span className="font-medium tabular-nums text-success">
            {activeCount}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Breached</span>
          <span
            className={cn(
              'font-medium tabular-nums',
              hasBreaches ? 'text-destructive' : 'text-muted-foreground',
            )}
          >
            {breachCount}
          </span>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Main Surface ─────────────────────────────────────────────────────────

export default function SlaWarRoomSurface() {
  const { data, loading, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.SLA_WAR_ROOM],
    normalizeSlaWarRoom,
    MOCK_SLA_WAR_ROOM,
    SURFACE_ID,
  )

  // Supplementary rich data (always from mock — no backend endpoint)
  const [timers] = useState<ActiveSlaTimer[]>(MOCK_SLA_TIMERS)
  const [breaches] = useState<BreachAlert[]>(MOCK_SLA_BREACHES)
  const [lastUpdated, setLastUpdated] = useState(new Date())

  // ── Derived metrics ──────────────────────────────────────────────────
  const totalTimers = data.breachTimers.length
  const breachedCount = data.breachTimers.filter(
    (t) => t.status === 'breached',
  ).length
  const atRiskCount = data.breachTimers.filter(
    (t) => t.status === 'warning',
  ).length
  const activeSlaCount = totalTimers - breachedCount - atRiskCount

  // Sort timers by urgency (overdue first, then ascending remaining)
  const sortedTimers = [...timers].sort((a, b) => {
    if (a.remainingSeconds <= 0 && b.remainingSeconds <= 0) return 0
    if (a.remainingSeconds <= 0) return -1
    if (b.remainingSeconds <= 0) return 1
    return a.remainingSeconds - b.remainingSeconds
  })

  // Build escalation level lookup from breach data
  const escalationMap = new Map<string, number>()
  for (const breach of breaches) {
    if (breach.escalationLevel > 0) {
      escalationMap.set(breach.ticketId, breach.escalationLevel)
    }
  }

  const handleRefresh = useCallback(() => {
    if (refresh) {
      refresh()
      setLastUpdated(new Date())
    }
  }, [refresh])

  // ── Loading ──
  if (loading) {
    return <LoadingSkeleton />
  }

  // ── Empty (only when source is backend and data is empty) ──
  if (
    source === 'backend' &&
    data.breachTimers.length === 0 &&
    data.activeSLAs.length === 0
  ) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  const operatingMode = data.operatingMode || (source === 'backend' ? 'live' : source === 'mock' ? 'demo' : 'degraded')
  const isDemo = operatingMode === 'demo'
  const isDegraded = operatingMode === 'degraded'

  // ── Content ──
  return (
    <div className="space-y-6">
      {/* Degraded fallback banner when backend failed */}
      {isDegraded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>
              Backend unavailable. Showing degraded SLA snapshot.
            </span>
          </div>
          <button
            onClick={handleRefresh}
            className="underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </motion.div>
      )}

      {/* ── 1. Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center flex-wrap gap-3"
      >
        <div className="flex items-center gap-2">
          <Timer className="h-5 w-5 text-chart-1" />
          <h2 className="text-lg font-semibold">SLA War Room</h2>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {/* Status badges */}
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-success/10 border border-success/20 text-success text-[10px] font-medium">
            <Activity className="h-3 w-3" />
            Active SLAs: {activeSlaCount}
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-medium',
              atRiskCount > 0
                ? 'bg-warning/10 border-warning/20 text-warning'
                : 'bg-muted border-border/50 text-muted-foreground',
            )}
          >
            <AlertTriangle className="h-3 w-3" />
            At Risk: {atRiskCount}
          </span>
          <span
            className={cn(
              'inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-medium',
              breachedCount > 0
                ? 'bg-destructive/10 border-destructive/20 text-destructive'
                : 'bg-muted border-border/50 text-muted-foreground',
            )}
          >
            <AlertOctagon className="h-3 w-3" />
            Breached: {breachedCount}
          </span>

          {/* Refresh + timestamp */}
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            title="Refresh data"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <span className="text-[10px] text-muted-foreground tabular-nums">
            {lastUpdated.toLocaleTimeString()}
          </span>

          <div className={cn(
            'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
            operatingMode === 'live' && 'bg-success/10 border-success/20 text-success',
            operatingMode === 'demo' && 'bg-warning/10 border-warning/20 text-warning',
            operatingMode === 'degraded' && 'bg-destructive/10 border-destructive/20 text-destructive',
          )}>
            <AlertTriangle className="h-3 w-3" />
            {operatingMode === 'live' ? 'Live' : operatingMode === 'demo' ? 'Demo' : 'Degraded'}
          </div>
        </div>
      </motion.div>

      {/* ── 2. Three-column Metric Bar ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="Active SLAs"
          value={activeSlaCount}
          sublabel={`${activeSlaCount} of ${totalTimers} within target`}
          color="success"
          icon={Shield}
          delay={0.1}
          circularValue={
            totalTimers > 0 ? (activeSlaCount / totalTimers) * 100 : 0
          }
        />
        <MetricCard
          label="At Risk"
          value={atRiskCount}
          sublabel={
            atRiskCount === 1
              ? '1 ticket approaching breach'
              : `${atRiskCount} tickets approaching breach`
          }
          color="warning"
          icon={AlertTriangle}
          delay={0.2}
          circularValue={
            totalTimers > 0 ? (atRiskCount / totalTimers) * 100 : 0
          }
        />
        <MetricCard
          label="Breached"
          value={breachedCount}
          sublabel={
            breachedCount === 1
              ? '1 SLA breached'
              : `${breachedCount} SLAs breached`
          }
          color="destructive"
          icon={AlertOctagon}
          delay={0.3}
          circularValue={
            totalTimers > 0 ? (breachedCount / totalTimers) * 100 : 0
          }
        />
      </div>

      {/* ── 3. SLA Breach Timers ── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.4 }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Clock className="h-4 w-4 text-chart-2" />
          <h3 className="text-sm font-semibold">SLA Breach Timers</h3>
          <span className="ml-auto text-xs text-muted-foreground">
            {sortedTimers.length} active
          </span>
        </div>
        <div className="space-y-2">
          {sortedTimers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
              <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
              <p className="text-xs">{t('empty.slaWarRoom')}</p>
            </div>
          ) : (
            <AnimatePresence>
              {sortedTimers.map((timer, idx) => (
                <BreachTimerRow
                  key={timer.ticketId}
                  timer={timer}
                  escalationLevel={
                    escalationMap.get(timer.ticketId) ?? 0
                  }
                  delay={0.05 * idx}
                />
              ))}
            </AnimatePresence>
          )}
        </div>
      </motion.div>

      {/* ── 4. Escalations + 5. Active SLAs ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Escalations */}
        <div className="lg:col-span-3 bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <ArrowUpRight className="h-4 w-4 text-warning" />
            <h3 className="text-sm font-semibold">Escalations</h3>
            <span className="ml-auto text-xs text-muted-foreground">
              {data.escalations.length} active
            </span>
          </div>
          <div className="divide-y divide-border/30">
            {data.escalations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
                <p className="text-xs">No active escalations</p>
              </div>
            ) : (
              data.escalations.map((esc, idx) => (
                <EscalationRow
                  key={esc.id}
                  ticketId={esc.ticketId}
                  level={esc.level}
                  reason={esc.reason}
                  escalatedAt={esc.escalatedAt}
                  delay={0.05 * idx}
                />
              ))
            )}
          </div>
        </div>

        {/* Active SLAs */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="h-4 w-4 text-chart-3" />
            <h3 className="text-sm font-semibold">Active SLAs</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {data.activeSLAs.length === 0 ? (
              <div className="col-span-full flex flex-col items-center justify-center py-10 text-muted-foreground">
                <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
                <p className="text-xs">No SLA definitions</p>
              </div>
            ) : (
              data.activeSLAs.map((sla, idx) => (
                <SlaDefinitionCard
                  key={sla.id}
                  name={sla.name}
                  targetSeconds={sla.targetSeconds}
                  activeCount={sla.activeCount}
                  breachCount={sla.breachCount}
                  delay={0.05 * idx}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
