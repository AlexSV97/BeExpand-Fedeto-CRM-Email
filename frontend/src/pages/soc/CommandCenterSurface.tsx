/**
 * CommandCenterSurface — SOC landing page.
 *
 * Production-quality dashboard with KPI cards, sparklines, recent alerts
 * feed, donut gauge for queue pressure, tier breakdown bars, and SLA risk
 * summary.  Uses useSocResource for data fetching with automatic mock
 * fallback.
 */

import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeCommandCenter } from '../../services/soc/normalize/commandCenter'
import type {
  CommandCenterKpiCardView,
  AlertItemView,
} from '../../services/soc/normalize/commandCenter'
import { MOCK_COMMAND_CENTER, MOCK_SLA_RISKS } from '../../services/soc/mockData'
import type { SlaRiskItem } from '../../services/soc/mockData'
import { SocEmptyState } from '../../components/soc'
import { applyNeutralCopy, t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Minus,
  Clock,
  AlertCircle,
  Shield,
  Gauge,
  AlertOctagon,
  LayoutDashboard,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatTimeAgo(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return t('time.justNow')
  if (diffMins < 60) return t('time.minAgo', { count: String(diffMins) })
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return t('time.hoursAgo', { count: String(diffHours) })
  const diffDays = Math.floor(diffHours / 24)
  return t('time.daysAgo', { count: String(diffDays) })
}

function formatTimeRemaining(seconds: number): string {
  if (seconds <= 0) return t('sla.breached')
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

function severityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'text-destructive bg-destructive/10 border-destructive/20'
    case 'warning':
      return 'text-warning bg-warning/10 border-warning/20'
    default:
      return 'text-chart-1 bg-chart-1/10 border-chart-1/20'
  }
}

function severityLabel(severity: string): string {
  return t(`severity.${severity}`)
}

function trendIcon(trend: 'up' | 'down' | 'stable') {
  switch (trend) {
    case 'up':
      return <ArrowUp className="h-3 w-3" />
    case 'down':
      return <ArrowDown className="h-3 w-3" />
    case 'stable':
      return <Minus className="h-3 w-3" />
  }
}

function formatLastUpdated(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function statusLabel(status: string): string {
  switch (status) {
    case 'operational':
      return 'Operational'
    case 'degraded':
      return 'Degraded'
    case 'error':
      return 'Error'
    default:
      return status.charAt(0).toUpperCase() + status.slice(1)
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────

/**
 * SVG donut/semi-circle gauge with color based on threshold.
 */
function DonutGauge({ value, size = 120 }: { value: number; size?: number }) {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (value / 100) * circumference
  const color = value < 50 ? '#22c55e' : value < 75 ? '#eab308' : '#ef4444'
  const center = size / 2

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        viewBox={`0 0 ${size} ${size}`}
      >
        {/* Background ring */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={8}
          className="text-muted/30"
        />
        {/* Value arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <span className="absolute text-2xl font-bold" style={{ color }}>
        {Math.round(value)}%
      </span>
    </div>
  )
}

/**
 * Mini SVG sparkline rendered from a data array.
 */
function Sparkline({
  data,
  color = 'currentColor',
}: {
  data: number[]
  color?: string
}) {
  if (!data || data.length < 2) return null

  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const points = data
    .map(
      (v, i) =>
        `${(i / (data.length - 1)) * 100},${((max - v) / range) * 100}`,
    )
    .join(' ')

  return (
    <svg viewBox="0 0 100 30" className="w-full h-8" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}

/**
 * Skeleton card placeholder for loading state.
 */
function SkeletonCard() {
  return (
    <div className="bg-card rounded-2xl p-5 border border-border/50 shadow-sm animate-pulse">
      <div className="space-y-3">
        <div className="h-3 w-20 bg-muted rounded" />
        <div className="h-8 w-24 bg-muted rounded" />
        <div className="h-6 w-full bg-muted/50 rounded mt-4" />
      </div>
    </div>
  )
}

/**
 * Enhanced KPI card with motion animation, trend badge, and sparkline.
 */
function KpiCard({
  card,
  index,
}: {
  card: CommandCenterKpiCardView
  index: number
}) {
  // Deterministic sparkline data that mirrors the trend direction
  const sparkData = useMemo(() => {
    return Array.from({ length: 8 }, (_, i) => {
      const base = card.value * 0.85
      const variance = card.value * 0.3
      const progress = i / 7
      if (card.trend === 'up') return base + variance * progress
      if (card.trend === 'down') return base + variance * (1 - progress)
      // stable → gentle wave pattern
      return base + variance * 0.5 + Math.sin(i * 0.9) * variance * 0.15
    })
  }, [card.value, card.trend])

  const sparkColor =
    card.trend === 'up'
      ? '#ef4444'
      : card.trend === 'down'
        ? '#22c55e'
        : '#6b7280'

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        delay: index * 0.1,
        duration: 0.4,
        ease: 'easeOut',
      }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={cn(
        'relative group bg-card rounded-2xl p-5 border border-border/50 shadow-sm overflow-hidden cursor-default',
        'transition-shadow duration-300 hover:shadow-lg',
      )}
    >
      {/* Gradient hover sheen */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-gradient-to-br from-chart-1/5 via-transparent to-chart-2/5" />

      <div className="relative space-y-2">
        {/* Label + trend badge row */}
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {applyNeutralCopy(card.label)}
          </p>
          {card.trend !== 'stable' && card.change != null && (
            <span
              className={cn(
                'inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
                card.trend === 'up'
                  ? 'bg-destructive/10 text-destructive'
                  : 'bg-success/10 text-success',
              )}
            >
              {trendIcon(card.trend)}
              {card.change}%
            </span>
          )}
        </div>

        {/* Primary value */}
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight">
            {card.value.toLocaleString('es-ES')}
          </span>
        </div>

        {/* Sparkline */}
        <div className="pt-1">
          <Sparkline data={sparkData} color={sparkColor} />
        </div>
      </div>
    </motion.div>
  )
}

/**
 * Single alert row with expand/collapse detail.
 */
function AlertFeedItem({ alert }: { alert: AlertItemView }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-start gap-3 w-full text-left px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors"
      >
        <div
          className={cn(
            'mt-0.5 rounded-full p-1 border shrink-0',
            severityColor(alert.severity),
          )}
        >
          {alert.severity === 'critical' ? (
            <AlertOctagon className="h-3 w-3" />
          ) : alert.severity === 'warning' ? (
            <AlertTriangle className="h-3 w-3" />
          ) : (
            <AlertCircle className="h-3 w-3" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground truncate">
            {applyNeutralCopy(alert.message)}
          </p>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={cn(
                'text-[10px] font-medium px-1.5 py-0.5 rounded',
                severityColor(alert.severity),
              )}
            >
              {severityLabel(alert.severity)}
            </span>
            <span className="text-[11px] text-muted-foreground">
              {formatTimeAgo(alert.timestamp)}
            </span>
          </div>
        </div>

        <div className="shrink-0 mt-1 text-muted-foreground">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </div>
      </button>

      {/* Expandable detail area */}
      {expanded && (
        <div className="px-4 py-2.5 bg-muted/20 border-b border-border/30 text-xs text-muted-foreground space-y-1">
          <p>
            <span className="font-medium text-foreground">ID:</span> {alert.id}
          </p>
          <p>
            <span className="font-medium text-foreground">Timestamp:</span>{' '}
            {new Date(alert.timestamp).toLocaleString('es-ES')}
          </p>
          <p>
            <span className="font-medium text-foreground">Severity:</span>{' '}
            {severityLabel(alert.severity)}
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * SLA risk row with breached / warning / normal state.
 */
function SlaRiskRow({ item }: { item: SlaRiskItem }) {
  const isBreached = item.remainingSeconds <= 0
  const isWarning = !isBreached && item.remainingSeconds < 7200

  return (
    <div
      className={cn(
        'flex items-center gap-4 px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors text-sm',
        isBreached && 'bg-destructive/5',
      )}
    >
      <div className="flex items-center gap-2 w-28 shrink-0">
        {isBreached ? (
          <AlertOctagon className="h-3.5 w-3.5 text-destructive" />
        ) : isWarning ? (
          <AlertTriangle className="h-3.5 w-3.5 text-warning" />
        ) : (
          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span
          className={cn(
            'font-mono text-xs font-medium',
            isBreached
              ? 'text-destructive'
              : isWarning
                ? 'text-warning'
                : 'text-foreground',
          )}
        >
          {item.ticketId}
        </span>
      </div>
      <span className="flex-1 truncate text-muted-foreground">
        {item.subject}
      </span>
      <span
        className={cn(
          'text-xs font-medium whitespace-nowrap',
          isBreached
            ? 'text-destructive'
            : isWarning
              ? 'text-warning'
              : 'text-muted-foreground',
        )}
      >
        {formatTimeRemaining(item.remainingSeconds)}
      </span>
    </div>
  )
}

/**
 * Status badge for the header (Operational / Degraded / Error).
 */
function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { label: string; classes: string; dotColor: string }> = {
    operational: {
      label: 'Operational',
      classes: 'bg-success/10 text-success border-success/20',
      dotColor: 'bg-success',
    },
    degraded: {
      label: 'Degraded',
      classes: 'bg-warning/10 text-warning border-warning/20',
      dotColor: 'bg-warning',
    },
    error: {
      label: 'Error',
      classes: 'bg-destructive/10 text-destructive border-destructive/20',
      dotColor: 'bg-destructive',
    },
  }

  const resolved = cfg[status] ?? {
    label: statusLabel(status),
    classes: 'bg-muted/10 text-muted-foreground border-border/20',
    dotColor: 'bg-muted-foreground',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full border',
        resolved.classes,
      )}
    >
      <span
        className={cn('h-1.5 w-1.5 rounded-full', resolved.dotColor)}
      />
      {resolved.label}
    </span>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.COMMAND_CENTER

export default function CommandCenterSurface() {
  const { setSurfaceStatus } = useSocShell()

  const { data, loading, error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.COMMAND_CENTER],
    normalizeCommandCenter,
    MOCK_COMMAND_CENTER,
    SURFACE_ID,
    // Extract SLA risk items from raw response if available
    (raw) => {
      const rawRecord = raw as Record<string, unknown>
      const rawSla = rawRecord.slaRiskSummary as unknown as SlaRiskItem[] | undefined
      if (rawSla && rawSla.length > 0) {
        setSlaRisks(rawSla)
      }
    },
  )

  // SLA risks start as mock; updated if backend provides them via onSuccess
  const [slaRisks, setSlaRisks] = useState<SlaRiskItem[]>(MOCK_SLA_RISKS)

  // Timestamp of the last successful data load
  const [lastUpdated, setLastUpdated] = useState(Date.now())

  // Update lastUpdated whenever loading transitions from true → false
  useEffect(() => {
    if (!loading) {
      setLastUpdated(Date.now())
    }
  }, [loading])

  // Sync surface status for the shell
  if (loading) {
    setSurfaceStatus(SURFACE_ID, 'loading')
  } else if (error) {
    setSurfaceStatus(SURFACE_ID, 'error')
  } else {
    setSurfaceStatus(SURFACE_ID, 'ready')
  }

  // ── Loading state (skeleton) ──────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-48 bg-muted rounded animate-pulse" />
            <div className="h-5 w-24 bg-muted rounded-full animate-pulse" />
          </div>
          <div className="h-8 w-20 bg-muted rounded-lg animate-pulse" />
        </div>

        {/* KPI skeleton cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  // ── Empty state ───────────────────────────────────────────────────

  if (data.kpiCards.length === 0 && data.recentAlerts.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Derived data ──────────────────────────────────────────────────

  // Per-tier breakdown derived from the overall queue pressure value.
  // Each tier represents a priority level with descending pressure.
  const tierData = [
    {
      label: 'N1',
      value: Math.min(100, Math.round(data.queuePressure * 0.9)),
    },
    {
      label: 'N2',
      value: Math.min(100, Math.round(data.queuePressure * 0.6)),
    },
    {
      label: 'N3',
      value: Math.min(100, Math.round(data.queuePressure * 0.35)),
    },
  ]

  // ── Content ───────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* ═══════════════════════════════════════════════════════════════
          Header Section
          ═══════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-chart-1/10 flex items-center justify-center">
            <LayoutDashboard className="h-5 w-5 text-chart-1" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">Command Center</h1>
            <p className="text-[11px] text-muted-foreground">
              Last updated: {formatLastUpdated(new Date(lastUpdated).toISOString())}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Operating mode indicator */}
          <span className={cn(
            'inline-flex items-center gap-1.5 text-[11px] font-medium',
            data.operatingMode === 'live' && 'text-success',
            data.operatingMode === 'demo' && 'text-warning',
            data.operatingMode === 'degraded' && 'text-destructive',
          )}>
            <span className={cn(
              'h-2 w-2 rounded-full',
              data.operatingMode === 'live' && 'bg-success animate-pulse',
              data.operatingMode === 'demo' && 'bg-warning',
              data.operatingMode === 'degraded' && 'bg-destructive',
            )} />
            {data.operatingMode === 'live' ? 'Live' : data.operatingMode === 'demo' ? 'Demo' : 'Degraded'}
          </span>

          {/* Surface status badge */}
          <StatusBadge status={data.surfaceStatus || 'operational'} />

          {/* Refresh button */}
          <button
            onClick={refresh}
            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-border/50 hover:bg-muted/50 transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          Source Banners
          ═══════════════════════════════════════════════════════════════ */}

      {/* Degraded fallback banner when backend failed */}
      {data.operatingMode === 'degraded' && (
        <div className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Backend unavailable. Showing degraded command-center snapshot.</span>
          </div>
          <button
            onClick={refresh}
            className="underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Demo banner when running with synthetic data */}
      {data.operatingMode === 'demo' && !error && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
          <AlertTriangle className="h-3.5 w-3.5" />
          {'Demo mode — data shown from local cache'}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          KPI Cards Row
          ═══════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {data.kpiCards.map((card, i) => (
          <KpiCard key={`${card.label}-${i}`} card={card} index={i} />
        ))}
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          Two-column layout: Recent Alerts + Queue Pressure
          ═══════════════════════════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Recent Alerts Feed (2/3) ───────────────────────────── */}
        <div className="lg:col-span-2 bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <Activity className="h-4 w-4 text-chart-1" />
            <h3 className="text-sm font-semibold">{t('commandCenter.recentAlerts')}</h3>
            <span className="ml-auto text-xs text-muted-foreground">
              {data.recentAlerts.length} {t('commandCenter.alerts')}
            </span>
          </div>

          <div className="divide-y divide-border/30">
            {data.recentAlerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
                <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
                <p className="text-xs">{t('empty.commandCenter.alerts')}</p>
              </div>
            ) : (
              data.recentAlerts.map((alert) => (
                <AlertFeedItem key={alert.id} alert={alert} />
              ))
            )}
          </div>

          {/* View All footer */}
          {data.recentAlerts.length > 0 && (
            <div className="px-4 py-2.5 border-t border-border/30">
              <button className="text-xs font-medium text-chart-1 hover:underline cursor-pointer">
                View All Alerts &rarr;
              </button>
            </div>
          )}
        </div>

        {/* ── Queue Pressure (1/3) ───────────────────────────────── */}
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <Gauge className="h-4 w-4 text-chart-3" />
            <h3 className="text-sm font-semibold">{t('commandCenter.queuePressure')}</h3>
          </div>

          <div className="p-6 flex flex-col items-center gap-5">
            {/* Donut gauge */}
            <DonutGauge value={data.queuePressure} size={120} />

            {/* Status description */}
            <p className="text-xs text-muted-foreground text-center leading-relaxed max-w-[200px]">
              {data.queuePressure >= 80
                ? t('commandCenter.pressureCritical')
                : data.queuePressure >= 50
                  ? t('commandCenter.pressureWarning')
                  : t('commandCenter.pressureNormal')}
            </p>

            {/* Per-tier breakdown bars */}
            <div className="w-full space-y-3">
              {tierData.map((tier) => {
                const barColor =
                  tier.value >= 80
                    ? 'bg-destructive'
                    : tier.value >= 50
                      ? 'bg-warning'
                      : 'bg-success'

                return (
                  <div key={tier.label} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-muted-foreground">
                        {tier.label}
                      </span>
                      <span className="font-semibold">{tier.value}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-700 ease-out',
                          barColor,
                        )}
                        style={{ width: `${tier.value}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          SLA Risk Summary
          ═══════════════════════════════════════════════════════════════ */}
      <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h3 className="text-sm font-semibold">{t('commandCenter.slaRiskSummary')}</h3>
          {slaRisks.length > 0 && (
            <span className="ml-auto text-xs text-muted-foreground">
              {slaRisks.filter((r) => r.remainingSeconds <= 0).length > 0 && (
                <span className="text-destructive font-medium mr-2">
                  {slaRisks.filter((r) => r.remainingSeconds <= 0).length}{' '}
                  {t('commandCenter.breached')}
                </span>
              )}
              {slaRisks.length} {t('commandCenter.atRisk')}
            </span>
          )}
        </div>

        {/* Column headers */}
        <div className="hidden sm:flex items-center gap-4 px-4 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b border-border/20 bg-muted/30">
          <span className="w-28 shrink-0">{t('commandCenter.ticketId')}</span>
          <span className="flex-1">{t('commandCenter.subject')}</span>
          <span className="whitespace-nowrap">
            {t('commandCenter.timeRemaining')}
          </span>
        </div>

        {slaRisks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
            <Shield className="h-8 w-8 mb-2 text-muted-foreground/40" />
            <p className="text-xs">{t('empty.commandCenter.sla')}</p>
          </div>
        ) : (
          <div className="divide-y divide-border/30">
            {slaRisks.map((item) => (
              <SlaRiskRow key={item.ticketId} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
