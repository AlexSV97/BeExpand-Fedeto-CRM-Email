/**
 * ConfigurationSurface — SOC settings UI.
 *
 * Professional settings interface with grouped configuration categories,
 * threshold cards, feature flag toggles, loading skeletons, and staggered
 * entrance animations.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeConfiguration } from '../../services/soc/normalize/configuration'
import { MOCK_CONFIGURATION } from '../../services/soc/mockData'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Settings,
  RefreshCw,
  AlertTriangle,
  Server,
  Mail,
  Bot,
  Gauge,
  Timer,
  Shield,
  Zap,
  Search,
  CheckCircle2,
  Clock,
  Cpu,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.CONFIGURATION

// ─── Motion variants ─────────────────────────────────────────────────────

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
}

const sectionVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
}

// ─── Types ────────────────────────────────────────────────────────────────

interface ThresholdItem {
  id: string
  name: string
  warning: number
  critical: number
  unit: string
}

interface FeatureFlagItem {
  id: string
  name: string
  description: string
  enabled: boolean
  Icon: React.ComponentType<{ className?: string }>
}

interface ConfigEntry {
  label: string
  value: string
  Icon: React.ComponentType<{ className?: string }>
}

interface SettingGroup {
  id: string
  title: string
  Icon: React.ComponentType<{ className?: string }>
  entries: ConfigEntry[]
}

// ─── Data ──────────────────────────────────────────────────────────────────

const SYSTEM_ENTRIES: ConfigEntry[] = [
  { label: 'Sync Interval', value: '30s', Icon: Timer },
  { label: 'Debug Mode', value: 'OFF', Icon: Shield },
  { label: 'Algorithm', value: 'default', Icon: Cpu },
  { label: 'Token Expiry', value: '30 min', Icon: Clock },
]

const EMAIL_ENTRIES: ConfigEntry[] = [
  { label: 'IMAP Server', value: 'imap.example.com', Icon: Mail },
  { label: 'IMAP Port', value: '993', Icon: Mail },
  { label: 'Poll Interval', value: '5 min', Icon: RefreshCw },
]

const AI_ENTRIES: ConfigEntry[] = [
  { label: 'Model', value: 'gpt-4', Icon: Bot },
]

const SETTING_GROUPS: SettingGroup[] = [
  { id: 'system', title: 'System Settings', Icon: Server, entries: SYSTEM_ENTRIES },
  { id: 'email', title: 'Email Integration', Icon: Mail, entries: EMAIL_ENTRIES },
  { id: 'ai', title: 'AI Configuration', Icon: Bot, entries: AI_ENTRIES },
]

const THRESHOLDS: ThresholdItem[] = [
  { id: 'sla-warning', name: 'SLA Warning', warning: 75, critical: 50, unit: '%' },
  { id: 'queue-pressure', name: 'Queue Pressure', warning: 60, critical: 85, unit: '%' },
  { id: 'backlog-ratio', name: 'Backlog Ratio', warning: 0.5, critical: 0.8, unit: '' },
]

const FEATURE_FLAGS: FeatureFlagItem[] = [
  { id: 'soc-enabled', name: 'SOC Enabled', description: 'Enable the Aiuken SOC shell', enabled: true, Icon: Shield },
  { id: 'auto-resolve', name: 'Auto Resolve', description: 'Auto-resolve tickets after SLA breach', enabled: false, Icon: Zap },
  { id: 'knowledge-search', name: 'Knowledge Search', description: 'Enable knowledge vault search', enabled: true, Icon: Search },
  { id: 'auto-approve', name: 'Auto Approve', description: 'Auto-approve low-risk agent recommendations', enabled: false, Icon: CheckCircle2 },
]

// ─── Sub-components ───────────────────────────────────────────────────────

function SkeletonSection() {
  return (
    <div className="rounded-2xl border border-border/50 shadow-sm overflow-hidden animate-pulse">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
        <div className="h-4 w-4 rounded bg-muted-foreground/20" />
        <div className="h-4 w-32 rounded bg-muted-foreground/20" />
      </div>
      <div className="p-5 space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="h-4 w-28 rounded bg-muted-foreground/20" />
            <div className="h-4 w-16 rounded bg-muted-foreground/20" />
          </div>
        ))}
      </div>
    </div>
  )
}

function SettingsGroupCard({ group }: { group: SettingGroup }) {
  const { Icon, title, entries } = group
  return (
    <motion.div
      variants={sectionVariants}
      className="rounded-2xl border border-border/50 shadow-sm overflow-hidden bg-card"
    >
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
        <Icon className="h-4 w-4 text-chart-1" />
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div className="p-5 space-y-4">
        {entries.map((entry) => (
          <div
            key={entry.label}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <entry.Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <span className="text-sm text-foreground">{entry.label}</span>
            </div>
            <span className="text-sm font-mono text-muted-foreground">
              {entry.value}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

function ThresholdCard({ threshold }: { threshold: ThresholdItem }) {
  const maxVal = Math.max(threshold.warning, threshold.critical, 100)
  const warnPct = (threshold.warning / maxVal) * 100
  const critPct = (threshold.critical / maxVal) * 100

  return (
    <div className="bg-card rounded-xl border border-border/50 shadow-sm p-4 flex flex-col gap-3">
      <span className="text-sm font-semibold text-foreground">
        {threshold.name}
      </span>

      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            <span className="text-muted-foreground">Warning</span>
          </span>
          <span className="font-mono font-medium text-amber-500">
            {threshold.warning}
            {threshold.unit}
          </span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span className="text-muted-foreground">Critical</span>
          </span>
          <span className="font-mono font-medium text-red-500">
            {threshold.critical}
            {threshold.unit}
          </span>
        </div>
      </div>

      <div className="relative h-2 w-full rounded-full bg-muted/50 overflow-hidden">
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-amber-400 rounded-full transition-all"
          style={{ left: `${warnPct}%` }}
        />
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-red-500 rounded-full transition-all"
          style={{ left: `${critPct}%` }}
        />
      </div>
    </div>
  )
}

function FeatureFlagCard({ flag }: { flag: FeatureFlagItem }) {
  const { Icon, name, description, enabled } = flag
  return (
    <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-border/20 last:border-b-0">
      <div className="flex items-start gap-3 min-w-0">
        <Icon
          className={cn(
            'h-4 w-4 mt-0.5 shrink-0',
            enabled ? 'text-primary' : 'text-muted-foreground',
          )}
        />
        <div className="space-y-0.5 min-w-0">
          <p className="text-sm font-semibold text-foreground">{name}</p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            {description}
          </p>
        </div>
      </div>

      <div
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          enabled ? 'bg-emerald-500' : 'bg-muted-foreground/30',
        )}
        aria-label={`${name}: ${enabled ? 'ON' : 'OFF'}`}
      >
        <span
          className={cn(
            'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
            enabled ? 'translate-x-[18px]' : 'translate-x-[3px]',
          )}
        />
      </div>
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function ConfigurationSurface() {
  const { loading, error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.CONFIGURATION],
    normalizeConfiguration,
    MOCK_CONFIGURATION,
    SURFACE_ID,
  )

  const [lastUpdated, setLastUpdated] = useState(new Date())

  const handleRefresh = () => {
    refresh()
    setLastUpdated(new Date())
  }

  const isDemo = source === 'mock'
  const hasError = error !== null

  // ── Loading ──

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">{t('surfaces.configuration')}</h2>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <SkeletonSection />
          <SkeletonSection />
          <SkeletonSection />
        </div>
      </div>
    )
  }

  // ── Content ──

  return (
    <motion.div
      className="space-y-4"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* ── Error banner ── */}
      {hasError && (
        <motion.div variants={sectionVariants}>
          <div className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium">
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
          </div>
        </motion.div>
      )}

      {/* ── Header ── */}
      <motion.div
        variants={sectionVariants}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Configuration</h2>
          {isDemo && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
              <AlertTriangle className="h-3.5 w-3.5" />
              Demo
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            Last updated {lastUpdated.toLocaleTimeString()}
          </span>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-xl transition-all cursor-pointer bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </motion.div>

      {/* ── Settings groups ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {SETTING_GROUPS.map((group) => (
          <SettingsGroupCard key={group.id} group={group} />
        ))}
      </div>

      {/* ── Thresholds ── */}
      <motion.div variants={sectionVariants}>
        <div className="flex items-center gap-2 mb-4">
          <Gauge className="h-4 w-4 text-chart-1" />
          <h3 className="text-sm font-semibold text-foreground">Thresholds</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {THRESHOLDS.map((threshold) => (
            <ThresholdCard key={threshold.id} threshold={threshold} />
          ))}
        </div>
      </motion.div>

      {/* ── Feature Flags ── */}
      <motion.div variants={sectionVariants}>
        <div className="flex items-center gap-2 mb-4">
          <Shield className="h-4 w-4 text-chart-1" />
          <h3 className="text-sm font-semibold text-foreground">Feature Flags</h3>
        </div>
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          {FEATURE_FLAGS.map((flag) => (
            <FeatureFlagCard key={flag.id} flag={flag} />
          ))}
        </div>
      </motion.div>
    </motion.div>
  )
}
