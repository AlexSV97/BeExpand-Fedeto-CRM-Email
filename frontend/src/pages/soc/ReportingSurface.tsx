/**
 * ReportingSurface — reporting and metrics dashboard.
 *
 * Features report type selector tabs, date range presets, recharts
 * visualisations (BarChart / LineChart), an export button, and a
 * metrics summary sidebar.
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSocShell } from '../../services/soc/SocShellProvider'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { socFetch } from '../../services/soc/client'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { normalizeReporting } from '../../services/soc/normalize/reporting'
import type { ReportingView } from '../../services/soc/normalize/reporting'
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

// ─── Mock chart data ──────────────────────────────────────────────────────

interface ChartDataPoint {
  name: string
  value: number
  secondary?: number
}

interface MockReportData {
  title: string
  icon: typeof BarChart3
  data: ChartDataPoint[]
  metrics: { label: string; value: string | number; icon: typeof BarChart3 }[]
}

const MOCK_REPORTS: Record<string, MockReportData> = {
  slaCompliance: {
    title: t('report.slaCompliance'),
    icon: CheckCircle,
    data: [
      { name: 'Network', value: 87 },
      { name: 'Security', value: 93 },
      { name: 'Applications', value: 82 },
      { name: 'Infrastructure', value: 91 },
      { name: 'Cloud', value: 78 },
    ],
    metrics: [
      { label: t('report.overallCompliance'), value: '86.2%', icon: CheckCircle },
      { label: t('report.totalTickets'), value: '1,284', icon: FileText },
      { label: t('report.breached'), value: '42', icon: Clock },
    ],
  },
  agentPerformance: {
    title: t('report.agentPerformance'),
    icon: Users,
    data: [
      { name: 'Ana L.', value: 94, secondary: 12 },
      { name: 'Carlos R.', value: 88, secondary: 8 },
      { name: 'Miguel T.', value: 76, secondary: 15 },
      { name: 'Laura G.', value: 92, secondary: 6 },
      { name: 'Diego F.', value: 71, secondary: 10 },
      { name: 'Valentina O.', value: 83, secondary: 9 },
    ],
    metrics: [
      { label: t('report.avgCompliance'), value: '84.0%', icon: TrendingUp },
      { label: t('report.activeAgents'), value: '6', icon: Users },
      { label: t('report.totalTickets'), value: '60', icon: FileText },
    ],
  },
  ticketVolume: {
    title: t('report.ticketVolume'),
    icon: BarChart3,
    data: [
      { name: 'Mon', value: 42 },
      { name: 'Tue', value: 56 },
      { name: 'Wed', value: 38 },
      { name: 'Thu', value: 61 },
      { name: 'Fri', value: 47 },
      { name: 'Sat', value: 22 },
      { name: 'Sun', value: 18 },
    ],
    metrics: [
      { label: t('report.totalTickets'), value: '284', icon: FileText },
      { label: t('report.dailyAvg'), value: '40.6', icon: BarChart3 },
      { label: t('report.peakDay'), value: 'Thu (61)', icon: TrendingUp },
    ],
  },
  queueTrends: {
    title: t('report.queueTrends'),
    icon: LineChart,
    data: [
      { name: 'Week 1', value: 45, secondary: 38 },
      { name: 'Week 2', value: 52, secondary: 42 },
      { name: 'Week 3', value: 38, secondary: 35 },
      { name: 'Week 4', value: 61, secondary: 48 },
    ],
    metrics: [
      { label: t('report.totalTickets'), value: '196', icon: FileText },
      { label: t('report.avgResolution'), value: '4.2h', icon: Clock },
      { label: t('report.slaCompliance'), value: '87%', icon: CheckCircle },
    ],
  },
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
  const { setSurfaceStatus } = useSocShell()
  const [data, setData] = useState<ReportingView | null>(null)
  const [error, setError] = useState<SocError | null>(null)
  const [loading, setLoading] = useState(true)

  // UI state
  const [activeReport, setActiveReport] = useState<string>('slaCompliance')
  const [activeRange, setActiveRange] = useState('30d')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    setSurfaceStatus(SURFACE_ID, 'loading')

    try {
      const raw = await socFetch<Record<string, unknown>>(SOC_ENDPOINTS[SURFACE_ID])
      const view = normalizeReporting(raw)
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

  // ── Handlers ──

  const handleExport = () => {
    console.log(`[Reporting] Export report: ${activeReport} (range: ${activeRange})`)
  }

  // ── Derived ──

  const currentReport = MOCK_REPORTS[activeReport]

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
            <Bar
              dataKey="value"
              fill="var(--chart-1)"
              radius={[4, 4, 0, 0]}
              name={t('report.value')}
            />
            {activeReport === 'agentPerformance' && (
              <Bar
                dataKey="secondary"
                fill="var(--chart-2)"
                radius={[4, 4, 0, 0]}
                name={t('report.ticketsHandled')}
              />
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
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--chart-1)"
              strokeWidth={2}
              dot={{ r: 3 }}
              name={t('report.queueA')}
            />
            <Line
              type="monotone"
              dataKey="secondary"
              stroke="var(--chart-2)"
              strokeWidth={2}
              dot={{ r: 3 }}
              name={t('report.queueB')}
            />
          </ReLineChart>
        )}
      </ResponsiveContainer>
    )
  }, [currentReport, activeReport])

  // ── Loading ──

  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.reporting')} />
  }

  // ── Error ──

  if (error) {
    return <SocErrorState error={error} />
  }

  // ── Empty ──

  if (!data || (data.metrics.length === 0 && data.reportTypes.length === 0)) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-chart-1" />
        <h2 className="text-lg font-semibold">{t('surfaces.reporting')}</h2>
      </div>

      {/* Report type selector */}
      <div className="flex flex-wrap items-center gap-2">
        {REPORT_TYPES.map((type) => (
          <ReportTypeTab
            key={type}
            active={activeReport === type}
            label={t(`report.${type}`)}
            icon={MOCK_REPORTS[type].icon}
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
          {/* Chart area */}
          <div className="lg:col-span-3 bg-card rounded-2xl border border-border/50 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-4">
              <currentReport.icon className="h-4 w-4 text-chart-1" />
              <h3 className="text-sm font-semibold">{currentReport.title}</h3>
            </div>
            <div className="h-[320px]">
              {chartContent}
            </div>
          </div>

          {/* Metrics summary */}
          <div className="space-y-3">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {t('report.metricsSummary')}
            </h4>
            {currentReport.metrics.map((metric, i) => (
              <MetricBadge
                key={i}
                label={metric.label}
                value={metric.value}
                icon={metric.icon}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
