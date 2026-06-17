/**
 * ReportingSurface — reporting and metrics dashboard.
 *
 * Features report type selector tabs, date range presets, recharts
 * visualisations (BarChart / LineChart), an export button, and a
 * metrics summary sidebar.
 */

import { useState, useMemo } from 'react'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeReporting } from '../../services/soc/normalize/reporting'
import { MOCK_REPORTING, MOCK_REPORTS_DATA } from '../../services/soc/mockData'
import { SocLoadingState, SocEmptyState, SocErrorState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  BarChart3,
  LineChart,
  Download,
  TrendingUp,
  Clock,
  CheckCircle,
  Users,
  FileText,
  Calendar,
  AlertTriangle,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  LineChart as ReLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.REPORTING

const REPORT_TYPES = ['slaCompliance', 'agentPerformance', 'ticketVolume', 'queueTrends'] as const

const DATE_RANGES = [
  { key: '7d', labelKey: 'report.last7Days' },
  { key: '30d', labelKey: 'report.last30Days' },
  { key: 'quarter', labelKey: 'report.lastQuarter' },
  { key: 'year', labelKey: 'report.thisYear' },
] as const

// ─── Map string icon names to lucide components ─────────────────────────

const ICON_MAP: Record<string, typeof BarChart3> = {
  CheckCircle,
  Users,
  BarChart3,
  LineChart,
  TrendingUp,
  Clock,
  FileText,
}

function resolveIcon(name: string): typeof BarChart3 {
  return ICON_MAP[name] ?? BarChart3
}

// ─── Sub-components ───────────────────────────────────────────────────────

function ReportTypeTab({
  active,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean
  label: string
  icon: typeof BarChart3
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
        active
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}

function DateRangePill({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
        active
          ? 'bg-muted text-foreground border-border'
          : 'bg-transparent text-muted-foreground border-transparent hover:text-foreground',
      )}
    >
      {label}
    </button>
  )
}

function MetricBadge({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string | number
  icon: typeof BarChart3
}) {
  return (
    <div className="flex items-center gap-3 bg-card rounded-xl border border-border/30 p-3">
      <div className="rounded-lg bg-chart-1/10 p-2 text-chart-1">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold text-foreground">{value}</p>
      </div>
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function ReportingSurface() {
  const { data, loading, error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.REPORTING],
    normalizeReporting,
    MOCK_REPORTING,
    SURFACE_ID,
  )

  // UI state
  const [activeReport, setActiveReport] = useState<string>('slaCompliance')
  const [activeRange, setActiveRange] = useState('30d')

  // ── Handlers ──
  const handleExport = () => {
    console.log(`[Reporting] Export report: ${activeReport} (range: ${activeRange})`)
  }

  // ── Derived ──
  const currentReport = MOCK_REPORTS_DATA[activeReport]
  const ActiveIconComponent = currentReport ? resolveIcon(currentReport.icon) : BarChart3

  const chartContent = useMemo(() => {
    if (!currentReport) return null
    const isBar = activeReport !== 'queueTrends'

    return (
      <ResponsiveContainer width="100%" height="100%">
        {isBar ? (
          <BarChart data={currentReport.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
            <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Bar dataKey="value" fill="var(--chart-1)" radius={[4, 4, 0, 0]} name={t('report.value')} />
            {activeReport === 'agentPerformance' && (
              <Bar dataKey="secondary" fill="var(--chart-2)" radius={[4, 4, 0, 0]} name={t('report.ticketsHandled')} />
            )}
          </BarChart>
        ) : (
          <ReLineChart data={currentReport.data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
            <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 3 }} name={t('report.queueA')} />
            <Line type="monotone" dataKey="secondary" stroke="var(--chart-2)" strokeWidth={2} dot={{ r: 3 }} name={t('report.queueB')} />
          </ReLineChart>
        )}
      </ResponsiveContainer>
    )
  }, [currentReport, activeReport])

  const isDemo = source === 'mock'

  // ── Loading ──
  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.reporting')} />
  }

  // ── Error ──
  if (error) {
    const socErr: SocError = { code: 'FETCH_ERROR', message: error, retry: refresh }
    return <SocErrorState error={socErr} />
  }

  // ── Empty (only when source is backend and data is empty) ──
  if (source === 'backend' && data.metrics.length === 0 && data.reportTypes.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <div className="space-y-4">
      {/* Header + demo badge */}
      <div className="flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-chart-1" />
        <h2 className="text-lg font-semibold">{t('surfaces.reporting')}</h2>
        {isDemo && (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            {"Demo"}
          </div>
        )}
      </div>

      {/* Report type selector */}
      <div className="flex flex-wrap items-center gap-2">
        {REPORT_TYPES.map((type) => (
          <ReportTypeTab
            key={type}
            active={activeReport === type}
            label={t(`report.${type}`)}
            icon={resolveIcon(MOCK_REPORTS_DATA[type]?.icon ?? 'BarChart3')}
            onClick={() => setActiveReport(type)}
          />
        ))}
      </div>

      {/* Date range + Export row */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-card rounded-2xl border border-border/50 shadow-sm px-4 py-2.5">
        <div className="flex items-center gap-1">
          <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
          {DATE_RANGES.map((range) => (
            <DateRangePill
              key={range.key}
              active={activeRange === range.key}
              label={t(range.labelKey)}
              onClick={() => setActiveRange(range.key)}
            />
          ))}
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer"
        >
          <Download className="h-3.5 w-3.5" />
          {t('report.exportReport')}
        </button>
      </div>

      {/* Main content */}
      {currentReport && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 bg-card rounded-2xl border border-border/50 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <ActiveIconComponent className="h-4 w-4 text-chart-1" />
              <h3 className="text-sm font-semibold">{currentReport.title}</h3>
            </div>
            <div className="h-[320px]">{chartContent}</div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {t('report.metricsSummary')}
            </h4>
            {currentReport.metrics.map((metric, i) => (
              <MetricBadge
                key={i}
                label={metric.label}
                value={metric.value}
                icon={resolveIcon(metric.icon)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

