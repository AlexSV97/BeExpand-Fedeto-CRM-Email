/**
 * ReportingSurface — Professional analytics dashboard.
 *
 * Displays key metrics, trend charts, and quick-access report actions.
 * Built with pure CSS bar charts, framer-motion animations, and a
 * responsive grid layout.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeReporting } from '../../services/soc/normalize/reporting'
import { MOCK_REPORTING } from '../../services/soc/mockData'
import { SocEmptyState } from '../../components/soc'
import { cn } from '../../lib/utils'
import {
  BarChart3,
  Download,
  RefreshCw,
  Calendar,
  FileText,
  Clock,
  CheckCircle,
  TrendingUp,
  AlertTriangle,
  Users,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.REPORTING

const REPORT_TYPE_TABS = ['Daily', 'Weekly', 'Monthly', 'SLA', 'Agent'] as const

// ─── Metric card mapping ────────────────────────────────────────────────

interface MetricCardData {
  label: string
  value: string
  icon: typeof BarChart3
  color: string
}

const METRIC_ICON_MAP: Record<string, { icon: typeof BarChart3; color: string }> = {
  'Total Tickets': { icon: BarChart3, color: 'from-blue-500 to-blue-600' },
  'Open Tickets': { icon: FileText, color: 'from-amber-500 to-amber-600' },
  'Pending Tickets': { icon: Clock, color: 'from-purple-500 to-purple-600' },
  'SLA Breaches': { icon: AlertTriangle, color: 'from-red-500 to-red-600' },
  'SLA Compliance Rate': { icon: CheckCircle, color: 'from-green-500 to-green-600' },
  'Avg Resolution Time': { icon: TrendingUp, color: 'from-cyan-500 to-cyan-600' },
}

// ─── Report action cards ─────────────────────────────────────────────────

interface ReportActionData {
  title: string
  description: string
  icon: typeof BarChart3
}

const REPORT_ACTIONS: ReportActionData[] = [
  { title: 'Run Daily Report', description: "Today's activity summary", icon: Calendar },
  { title: 'Run Weekly Report', description: '7-day performance overview', icon: FileText },
  { title: 'Run Monthly Report', description: 'Monthly trends & KPIs', icon: BarChart3 },
  { title: 'Export SLA Report', description: 'SLA compliance details', icon: CheckCircle },
  { title: 'Export Agent Report', description: 'Agent performance metrics', icon: Users },
]

// ─── Animation variants ──────────────────────────────────────────────────

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

// ─── Pure CSS Bar Chart ──────────────────────────────────────────────────

function BarChart({
  data,
  label,
  color = 'bg-primary',
}: {
  data: { label: string; value: number }[]
  label: string
  color?: string
}) {
  const max = Math.max(...data.map((d) => d.value), 1)
  return (
    <div className="bg-card rounded-2xl border p-4">
      <h3 className="text-sm font-medium mb-4">{label}</h3>
      <div className="flex items-end gap-2 h-40">
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div
              className={`w-full rounded-t transition-all duration-500 ${color}`}
              style={{ height: `${(d.value / max) * 100}%`, minHeight: '4px' }}
            />
            <span className="text-[10px] text-muted-foreground">{d.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Metric Card ─────────────────────────────────────────────────────────

function MetricCard({ label, value, icon: Icon, color }: MetricCardData) {
  return (
    <motion.div
      variants={itemVariants}
      className="bg-card rounded-2xl border p-4"
    >
      <div className="flex items-center gap-3">
        <div
          className={`h-12 w-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center shadow-sm`}
        >
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Skeleton Components ─────────────────────────────────────────────────

function SkeletonMetricCard() {
  return (
    <div className="bg-card rounded-2xl border p-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-xl bg-muted" />
        <div className="space-y-2">
          <div className="h-7 w-20 rounded bg-muted" />
          <div className="h-3 w-16 rounded bg-muted" />
        </div>
      </div>
    </div>
  )
}

function SkeletonChart() {
  return (
    <div className="bg-card rounded-2xl border p-4 animate-pulse">
      <div className="h-4 w-32 rounded bg-muted mb-4" />
      <div className="flex items-end gap-2 h-40">
        {[55, 70, 50, 80, 65, 40, 30].map((h, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-1">
            <div className="w-full rounded-t bg-muted" style={{ height: `${h}%` }} />
          </div>
        ))}
      </div>
    </div>
  )
}

function SkeletonReportAction() {
  return (
    <div className="bg-card rounded-2xl border p-5 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-muted" />
        <div className="space-y-2 flex-1">
          <div className="h-4 w-36 rounded bg-muted" />
          <div className="h-3 w-24 rounded bg-muted" />
        </div>
      </div>
    </div>
  )
}

function SkeletonLayout() {
  return (
    <div className="space-y-4">
      {/* Header skeleton */}
      <div className="flex items-center justify-between animate-pulse">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 rounded bg-muted" />
          <div className="h-6 w-48 rounded bg-muted" />
        </div>
      </div>
      {/* Tabs skeleton */}
      <div className="flex gap-2 animate-pulse">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-9 w-24 rounded-lg bg-muted" />
        ))}
      </div>
      {/* Metrics grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {[...Array(6)].map((_, i) => (
          <SkeletonMetricCard key={i} />
        ))}
      </div>
      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonChart />
        <SkeletonChart />
      </div>
      {/* Report actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <SkeletonReportAction key={i} />
        ))}
      </div>
    </div>
  )
}

// ─── Main Surface ────────────────────────────────────────────────────────

export default function ReportingSurface() {
  const { data, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.REPORTING],
    normalizeReporting,
    MOCK_REPORTING,
    SURFACE_ID,
  )

  // UI state
  const [activeTab, setActiveTab] = useState<string>('Daily')
  const today = new Date().toISOString().split('T')[0]
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split('T')[0]
  const [dateFrom, setDateFrom] = useState(weekAgo)
  const [dateTo, setDateTo] = useState(today)
  const [lastUpdated, setLastUpdated] = useState<string>(
    new Date().toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }),
  )

  // Handlers
  const handleRefresh = () => {
    refresh()
    setLastUpdated(
      new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    )
  }

  const handleExport = () => {
    console.log(
      `[Reporting] Export report: ${activeTab} (from: ${dateFrom}, to: ${dateTo})`,
    )
  }

  const operatingMode = data.operatingMode || (source === 'backend' ? 'live' : source === 'mock' ? 'demo' : 'degraded')
  const isDemo = operatingMode === 'demo'
  const isDegraded = operatingMode === 'degraded'

  const metricCards: MetricCardData[] = data.metrics.map((metric) => {
    const config = METRIC_ICON_MAP[metric.label] || { icon: BarChart3, color: 'from-slate-500 to-slate-600' }
    const formattedValue = metric.unit === '%'
      ? `${metric.value.toFixed(1)}%`
      : metric.unit
        ? `${metric.value.toFixed(1)}${metric.unit}`
        : metric.value.toFixed(0)

    return {
      label: metric.label,
      value: formattedValue,
      icon: config.icon,
      color: config.color,
    }
  })

  const ticketVolumeData = data.trends
    .filter((item) => item.metric === 'ticket_volume')
    .map((item) => ({ label: item.date.slice(5), value: item.value }))

  const slaComplianceData = data.trends
    .filter((item) => item.metric === 'sla_compliance')
    .map((item) => ({ label: item.date.slice(5), value: item.value }))

  // ── Loading ──
  if (loading) {
    return <SkeletonLayout />
  }

  // ── Empty (only when source is backend and data is empty) ──
  if (
    source === 'backend' &&
    data.metrics.length === 0 &&
    data.reportTypes.length === 0
  ) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-4"
    >
      {/* Degraded banner when backend failed and we fell back */}
      {isDegraded && (
        <motion.div
          variants={itemVariants}
          className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Backend unavailable. Showing degraded analytics snapshot.</span>
          </div>
          <button
            onClick={handleRefresh}
            className="underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </motion.div>
      )}

      {/* Header */}
      <motion.div
        variants={itemVariants}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-sm">
            <BarChart3 className="h-4 w-4 text-white" />
          </div>
          <h2 className="text-lg font-semibold">Reporting &amp; Analytics</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border/50 hover:bg-muted transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          <span className="text-[10px] text-muted-foreground">
            Updated {lastUpdated}
          </span>
          <div className={cn(
            'flex items-center gap-2 px-3 py-1 rounded-lg text-xs font-medium border',
            operatingMode === 'live' && 'bg-success/10 border-success/20 text-success',
            operatingMode === 'demo' && 'bg-warning/10 border-warning/20 text-warning',
            operatingMode === 'degraded' && 'bg-destructive/10 border-destructive/20 text-destructive',
          )}>
            <AlertTriangle className="h-3.5 w-3.5" />
            {operatingMode === 'live' ? 'Live' : operatingMode === 'demo' ? 'Demo' : 'Degraded'}
          </div>
        </div>
      </motion.div>

      {/* Report type tabs + Date range */}
      <motion.div
        variants={itemVariants}
        className="flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex flex-wrap items-center gap-2">
          {REPORT_TYPE_TABS.map((type) => (
            <button
              key={type}
              onClick={() => setActiveTab(type)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
                activeTab === type
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
              )}
            >
              {type}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5" />
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="bg-card border border-border/50 rounded-lg px-2 py-1.5 text-xs text-foreground w-32 cursor-pointer"
            />
            <span>to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="bg-card border border-border/50 rounded-lg px-2 py-1.5 text-xs text-foreground w-32 cursor-pointer"
            />
          </div>
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer"
          >
            <Download className="h-3.5 w-3.5" />
            Export
          </button>
        </div>
      </motion.div>

      {/* Key metrics row */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"
      >
        {metricCards.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </motion.div>

      {/* Charts section — two-column layout */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 lg:grid-cols-2 gap-4"
      >
        <BarChart
          data={ticketVolumeData}
          label="Ticket Volume (7-day trend)"
          color="bg-gradient-to-t from-blue-500 to-blue-400"
        />
        <BarChart
          data={slaComplianceData}
          label="SLA Compliance (7-day trend)"
          color="bg-gradient-to-t from-green-500 to-green-400"
        />
      </motion.div>

      {/* Report types quick-access */}
      <motion.div
        variants={itemVariants}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4"
      >
        {REPORT_ACTIONS.map((action) => (
          <button
            key={action.title}
            onClick={() =>
              console.log(`[Reporting] ${action.title}`)
            }
            className="bg-card rounded-2xl border p-5 text-left hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-muted flex items-center justify-center group-hover:bg-primary/10 transition-colors">
                <action.icon className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">{action.title}</p>
                <p className="text-xs text-muted-foreground">{action.description}</p>
              </div>
            </div>
          </button>
        ))}
      </motion.div>
    </motion.div>
  )
}
