/**
 * CommandCenterSurface — SOC landing page.
 *
 * Shows KPI cards, recent alerts feed, queue pressure gauge,
 * and SLA risk summary.  Uses useSocResource for data fetching
 * with automatic mock fallback.
 */

import { useState } from 'react'
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
import { SocLoadingState, SocEmptyState } from '../../components/soc'
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
      return <ArrowUp className="h-3.5 w-3.5" />
    case 'down':
      return <ArrowDown className="h-3.5 w-3.5" />
    case 'stable':
      return <Minus className="h-3.5 w-3.5" />
  }
}

function trendColor(trend: 'up' | 'down' | 'stable'): string {
  switch (trend) {
    case 'up':
      return 'text-destructive'
    case 'down':
      return 'text-success'
    case 'stable':
      return 'text-muted-foreground'
  }
}

function queuePressureTextColor(pct: number): string {
  if (pct >= 80) return 'text-destructive'
  if (pct >= 50) return 'text-warning'
  return 'text-success'
}

// ─── Sub-components ───────────────────────────────────────────────────────

function KpiCard({ card }: { card: CommandCenterKpiCardView }) {
  const animatedValue = card.value

  return (
    <div
      className={cn(
        'relative group bg-card rounded-2xl p-5 border border-border/50 shadow-sm overflow-hidden',
        'transition-all duration-300 hover:shadow-md hover:-translate-y-0.5',
      )}
    >
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-gradient-to-br from-chart-1/5 via-transparent to-chart-2/5" />

      <div className="relative space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {applyNeutralCopy(card.label)}
        </p>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-bold tracking-tight">
            {animatedValue.toLocaleString('es-ES')}
          </span>
          {card.trend !== 'stable' && (
            <span className={cn('inline-flex items-center gap-0.5 text-xs font-medium', trendColor(card.trend))}>
              {trendIcon(card.trend)}
              {card.change != null && `${card.change}%`}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function AlertFeedItem({ alert }: { alert: AlertItemView }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors">
      <div className={cn('mt-0.5 rounded-full p-1 border', severityColor(alert.severity))}>
        {alert.severity === 'critical' ? (
          <AlertOctagon className="h-3 w-3" />
        ) : alert.severity === 'warning' ? (
          <AlertTriangle className="h-3 w-3" />
        ) : (
          <AlertCircle className="h-3 w-3" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground truncate">{applyNeutralCopy(alert.message)}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', severityColor(alert.severity))}>
            {severityLabel(alert.severity)}
          </span>
          <span className="text-[11px] text-muted-foreground">{formatTimeAgo(alert.timestamp)}</span>
        </div>
      </div>
    </div>
  )
}

function SlaRiskRow({ item }: { item: SlaRiskItem }) {
  const isBreached = item.remainingSeconds <= 0
  const isWarning = !isBreached && item.remainingSeconds < 7200

  return (
    <div className={cn(
      'flex items-center gap-4 px-4 py-3 border-b border-border/30 last:border-b-0 hover:bg-muted/50 transition-colors text-sm',
      isBreached && 'bg-destructive/5',
    )}>
      <div className="flex items-center gap-2 w-28 shrink-0">
        {isBreached ? (
          <AlertOctagon className="h-3.5 w-3.5 text-destructive" />
        ) : isWarning ? (
          <AlertTriangle className="h-3.5 w-3.5 text-warning" />
        ) : (
          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span className={cn(
          'font-mono text-xs font-medium',
          isBreached ? 'text-destructive' : isWarning ? 'text-warning' : 'text-foreground',
        )}>
          {item.ticketId}
        </span>
      </div>
      <span className="flex-1 truncate text-muted-foreground">{item.subject}</span>
      <span className={cn(
        'text-xs font-medium whitespace-nowrap',
        isBreached ? 'text-destructive' : isWarning ? 'text-warning' : 'text-muted-foreground',
      )}>
        {formatTimeRemaining(item.remainingSeconds)}
      </span>
    </div>
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

  // Sync surface status for the shell
  if (loading) {
    setSurfaceStatus(SURFACE_ID, 'loading')
  } else if (error) {
    setSurfaceStatus(SURFACE_ID, 'error')
  } else {
    setSurfaceStatus(SURFACE_ID, 'ready')
  }

  // ── Loading state ─────────────────────────────────────────────────

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.commandCenter')} />
  }

  // ── Error state ───────────────────────────────────────────────────
  // NOTE: no early return — useSocResource always provides mock data,
  // so we show data + error banner instead of a hard error block.

  // ── Empty state ───────────────────────────────────────────────────

  if (data.kpiCards.length === 0 && data.recentAlerts.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──────────────────────────────────────────────────────

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

      {/* Demo badge when source is mock */}
      {source === 'mock' && (
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
          <AlertTriangle className="h-3.5 w-3.5" />
          {"Demo mode — data shown from local cache"}
        </div>
      )}

      {/* KPI Cards row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {data.kpiCards.map((card, i) => (
          <KpiCard key={`${card.label}-${i}`} card={card} />
        ))}
      </div>

      {/* Middle row: Recent Alerts + Queue Pressure */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Alerts Feed */}
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
        </div>

        {/* Queue Pressure Gauge */}
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
            <Gauge className="h-4 w-4 text-chart-3" />
            <h3 className="text-sm font-semibold">{t('commandCenter.queuePressure')}</h3>
          </div>
          <div className="p-6 flex flex-col items-center justify-center gap-4">
            <div className="relative w-32 h-32">
              <svg className="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="52" fill="none" stroke="oklch(0.9 0.002 90)" strokeWidth="10" />
                <circle
                  cx="60" cy="60" r="52" fill="none" stroke="currentColor" strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(data.queuePressure / 100) * 326.73} 326.73`}
                  className={queuePressureTextColor(data.queuePressure)}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={cn('text-2xl font-bold', queuePressureTextColor(data.queuePressure))}>
                  {Math.round(data.queuePressure)}%
                </span>
                <span className="text-[10px] text-muted-foreground uppercase tracking-wider mt-0.5">
                  {t('commandCenter.pressure')}
                </span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground text-center leading-relaxed max-w-[180px]">
              {data.queuePressure >= 80
                ? t('commandCenter.pressureCritical')
                : data.queuePressure >= 50
                  ? t('commandCenter.pressureWarning')
                  : t('commandCenter.pressureNormal')}
            </p>
          </div>
        </div>
      </div>

      {/* SLA Risk Summary */}
      <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h3 className="text-sm font-semibold">{t('commandCenter.slaRiskSummary')}</h3>
          {slaRisks.length > 0 && (
            <span className="ml-auto text-xs text-muted-foreground">
              {slaRisks.filter((r) => r.remainingSeconds <= 0).length > 0 && (
                <span className="text-destructive font-medium mr-2">
                  {slaRisks.filter((r) => r.remainingSeconds <= 0).length} {t('commandCenter.breached')}
                </span>
              )}
              {slaRisks.length} {t('commandCenter.atRisk')}
            </span>
          )}
        </div>

        <div className="hidden sm:flex items-center gap-4 px-4 py-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b border-border/20 bg-muted/30">
          <span className="w-28 shrink-0">{t('commandCenter.ticketId')}</span>
          <span className="flex-1">{t('commandCenter.subject')}</span>
          <span className="whitespace-nowrap">{t('commandCenter.timeRemaining')}</span>
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

