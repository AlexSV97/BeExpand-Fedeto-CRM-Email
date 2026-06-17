/**
 * AgentGovernanceSurface — professional agent monitoring UI.
 *
 * Displays a compliance summary, agent card grid with heartbeat and
 * permission scopes, and an expandable permission matrix.
 */

import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { SURFACE_IDS } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeAgentGovernance } from '../../services/soc/normalize/agentGovernance'
import { MOCK_AGENT_GOVERNANCE } from '../../services/soc/mockData'
import type { PermissionSetView } from '../../services/soc/normalize/agentGovernance'
import { SocEmptyState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Shield,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Check,
  Clock,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.AGENT_GOVERNANCE

const STATUS_CONFIG = {
  active: {
    dot: 'bg-emerald-500',
    border: 'border-l-emerald-500',
    badge: 'bg-emerald-500/10 text-emerald-600',
    label: 'Active',
  },
  paused: {
    dot: 'bg-amber-500',
    border: 'border-l-amber-500',
    badge: 'bg-amber-500/10 text-amber-600',
    label: 'Paused',
  },
  error: {
    dot: 'bg-red-500',
    border: 'border-l-red-500',
    badge: 'bg-red-500/10 text-red-600',
    label: 'Error',
  },
} as const

// ─── Motion variants ─────────────────────────────────────────────────────

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function formatTimeAgo(iso: string): string {
  const now = new Date()
  const diffMs = now.getTime() - new Date(iso).getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  if (diffSecs < 5) return 'just now'
  if (diffSecs < 60) return `${diffSecs}s ago`
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function getAgentScopes(agentId: string, permissions: PermissionSetView[]): string[] {
  return permissions.find((p) => p.agentId === agentId)?.scopes ?? []
}

// ─── Sub-components ───────────────────────────────────────────────────────

/**
 * SVG mini-ring donut chart showing passed / total compliance ratio.
 */
function DonutChart({
  passed,
  total,
  size = 56,
}: {
  passed: number
  total: number
  size?: number
}) {
  const strokeWidth = 5
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const ratio = total > 0 ? passed / total : 1
  const offset = circumference * (1 - ratio)

  return (
    <svg width={size} height={size} className="shrink-0" aria-label={`${Math.round(ratio * 100)}% compliance`}>
      {/* Background ring */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        className="text-destructive/20"
      />
      {/* Progress arc */}
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
        className="text-emerald-500"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      {/* Centre percentage */}
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className="fill-current text-[11px] font-bold tabular-nums"
      >
        {Math.round(ratio * 100)}%
      </text>
    </svg>
  )
}

/**
 * Skeleton placeholder for loading state.
 */
function SkeletonAgentCard() {
  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4 animate-pulse">
      {/* Name row */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground/20" />
        <div className="h-4 bg-muted-foreground/20 rounded w-28" />
      </div>
      {/* Status badge */}
      <div className="h-5 bg-muted-foreground/20 rounded w-14 mb-3" />
      {/* Scope tags */}
      <div className="space-y-1.5 mb-3">
        <div className="h-3.5 bg-muted-foreground/20 rounded w-20" />
        <div className="h-3.5 bg-muted-foreground/20 rounded w-24" />
        <div className="h-3.5 bg-muted-foreground/20 rounded w-16" />
      </div>
      {/* Heartbeat */}
      <div className="h-3 bg-muted-foreground/20 rounded w-24" />
    </div>
  )
}

/**
 * Single agent card with status dot, badge, permission scopes, and heartbeat.
 */
function AgentCard({
  agent,
  scopes,
  statusKey,
}: {
  agent: { id: string; name: string; status: string; lastHeartbeat: string }
  scopes: string[]
  statusKey: keyof typeof STATUS_CONFIG
}) {
  const config = STATUS_CONFIG[statusKey] ?? STATUS_CONFIG.error

  return (
    <motion.div
      variants={cardVariants}
      className={cn(
        'bg-card rounded-2xl border border-border/50 shadow-sm p-4 border-l-4 transition-shadow hover:shadow-md',
        config.border,
      )}
    >
      {/* Header: dot + name */}
      <div className="flex items-center gap-2 mb-2">
        <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', config.dot)} />
        <span className="text-sm font-semibold text-foreground truncate">
          {agent.name}
        </span>
      </div>

      {/* Status badge */}
      <span
        className={cn(
          'inline-block text-[10px] font-medium px-2 py-0.5 rounded mb-3',
          config.badge,
        )}
      >
        {config.label}
      </span>

      {/* Permission scopes */}
      <div className="flex flex-wrap gap-1 mb-3 min-h-[2.25rem]">
        {scopes.length > 0 ? (
          scopes.map((scope) => (
            <span
              key={scope}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground border border-border/30"
            >
              {scope}
            </span>
          ))
        ) : (
          <span className="text-[10px] text-muted-foreground/40 italic self-end">
            No permissions
          </span>
        )}
      </div>

      {/* Last heartbeat */}
      <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
        <Clock className="h-3 w-3" />
        <span>Last: {formatTimeAgo(agent.lastHeartbeat)}</span>
      </div>
    </motion.div>
  )
}

// ─── Permission Matrix ────────────────────────────────────────────────────

const SCOPE_CATEGORIES = [
  { key: 'triage', label: 'Triage', patterns: ['alert', 'triage'] },
  { key: 'sla', label: 'SLA', patterns: ['sla'] },
  { key: 'knowledge', label: 'Knowledge', patterns: ['knowledge'] },
  { key: 'ticket', label: 'Ticket', patterns: ['ticket'] },
  { key: 'escalation', label: 'Escalation', patterns: ['escalate'] },
  { key: 'audit', label: 'Audit', patterns: ['audit'] },
  { key: 'compliance', label: 'Compliance', patterns: ['compliance'] },
] as const

function hasCategoryScope(scopes: string[], patterns: readonly string[]): boolean {
  return scopes.some((s) => patterns.some((p) => s.toLowerCase().includes(p)))
}

function PermissionMatrix({
  agents,
  permissions,
}: {
  agents: { id: string; name: string }[]
  permissions: PermissionSetView[]
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full px-4 py-3 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
      >
        <span>Permission Matrix</span>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
      </button>

      {expanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div className="overflow-x-auto px-4 pb-4">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border/20">
                  <th className="text-left py-2 pr-4 text-muted-foreground font-medium">
                    Scope
                  </th>
                  {agents.map((a) => (
                    <th
                      key={a.id}
                      className="text-center py-2 px-2 text-muted-foreground font-medium whitespace-nowrap"
                    >
                      {a.name.split(' ')[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SCOPE_CATEGORIES.map((cat) => (
                  <tr
                    key={cat.key}
                    className="border-b border-border/10 last:border-0"
                  >
                    <td className="py-2 pr-4 text-foreground font-medium">
                      {cat.label}
                    </td>
                    {agents.map((a) => {
                      const agentScopes = getAgentScopes(a.id, permissions)
                      const has = hasCategoryScope(agentScopes, cat.patterns)
                      return (
                        <td key={a.id} className="text-center py-2 px-2">
                          {has ? (
                            <Check className="h-3.5 w-3.5 text-emerald-500 mx-auto" />
                          ) : (
                            <span className="inline-block h-3.5 w-3.5" />
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function AgentGovernanceSurface() {
  const { data, loading, error: _error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.AGENT_GOVERNANCE],
    normalizeAgentGovernance,
    MOCK_AGENT_GOVERNANCE,
    SURFACE_ID,
  )

  const agents = data.agents
  const permissions = data.permissions
  const compliance = data.compliance
  const isDemo = source === 'mock'
  const totalCompliance = compliance.passed + compliance.failed

  // Latest heartbeat across all agents
  const lastUpdated = useMemo(() => {
    if (agents.length === 0) return ''
    const latest = agents.reduce((latest, a) =>
      a.lastHeartbeat > latest ? a.lastHeartbeat : latest,
      agents[0].lastHeartbeat,
    )
    return formatTimeAgo(latest)
  }, [agents])

  // Stable status key (fallback for unknown statuses)
  const toStatusKey = (s: string): keyof typeof STATUS_CONFIG => {
    if (s === 'active' || s === 'paused' || s === 'error') return s
    return 'error'
  }

  // ── Loading ──
  if (loading) {
    return (
      <div className="space-y-4">
        {/* Skeleton header */}
        <div className="flex items-center gap-2">
          <div className="h-5 w-5 rounded bg-muted-foreground/20 animate-pulse" />
          <div className="h-5 bg-muted-foreground/20 animate-pulse rounded w-40" />
          <div className="h-4 bg-muted-foreground/20 animate-pulse rounded w-16" />
          <div className="h-4 bg-muted-foreground/20 animate-pulse rounded w-24" />
          <div className="ml-auto flex items-center gap-2">
            <div className="h-6 w-6 bg-muted-foreground/20 animate-pulse rounded" />
            <div className="h-3 bg-muted-foreground/20 animate-pulse rounded w-20" />
          </div>
        </div>

        {/* Skeleton compliance bar */}
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 bg-muted-foreground/20 animate-pulse rounded-full" />
            <div className="flex items-center gap-6">
              <div className="h-3 w-16 bg-muted-foreground/20 animate-pulse rounded" />
              <div className="h-3 w-16 bg-muted-foreground/20 animate-pulse rounded" />
            </div>
            <div className="ml-auto space-y-1.5">
              <div className="h-3 w-28 bg-muted-foreground/20 animate-pulse rounded ml-auto" />
              <div className="h-3 w-20 bg-muted-foreground/20 animate-pulse rounded ml-auto" />
            </div>
          </div>
        </div>

        {/* Skeleton agent card grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonAgentCard key={i} />
          ))}
        </div>
      </div>
    )
  }

  // ── Empty (only when source is backend and genuinely empty) ──
  if (source === 'backend' && agents.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className="space-y-4"
    >
      {/* ── Error banner (preserved from original) ── */}
      {source === 'error' && (
        <motion.div
          variants={cardVariants}
          className="flex items-center justify-between px-4 py-2 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-xs font-medium"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Failed to load data from server. Showing cached/demo data.</span>
          </div>
          <button
            onClick={refresh}
            className="underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </motion.div>
      )}

      {/* ── 1. Header ── */}
      <motion.div
        variants={cardVariants}
        className="flex items-center gap-2 flex-wrap"
      >
        <Shield className="h-5 w-5 text-chart-3" />
        <h2 className="text-lg font-semibold">
          {t('surfaces.agentGovernance')}
        </h2>

        {/* Agent count */}
        <span className="text-xs text-muted-foreground">
          {agents.length} {agents.length === 1 ? 'Agent' : 'Agents'}
        </span>

        {/* Compliance badge */}
        <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border/50">
          Compliance: {compliance.passed}/{totalCompliance}
        </span>

        {/* Demo badge */}
        {isDemo && (
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-warning/10 border border-warning/20 text-warning text-[10px] font-medium">
            <AlertTriangle className="h-3 w-3" />
            Demo
          </div>
        )}

        {/* Refresh + last updated */}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={refresh}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
            title="Refresh agent data"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {lastUpdated && (
            <span className="text-[10px] text-muted-foreground whitespace-nowrap">
              Updated {lastUpdated}
            </span>
          )}
        </div>
      </motion.div>

      {/* ── 2. Compliance bar ── */}
      <motion.div
        variants={cardVariants}
        className="bg-card rounded-2xl border border-border/50 shadow-sm p-4"
      >
        <div className="flex items-center gap-4 flex-wrap">
          {/* Donut mini-ring chart */}
          <DonutChart passed={compliance.passed} total={totalCompliance} size={56} />

          {/* Passed / Failed counts */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-xs text-muted-foreground">
                {compliance.passed} Passed
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-red-500 shrink-0" />
              <span className="text-xs text-muted-foreground">
                {compliance.failed} Failed
              </span>
            </div>
          </div>

          {/* Compliance report + View Report */}
          <div className="ml-auto text-right">
            <p className="text-xs font-medium text-foreground">
              Compliance Report
            </p>
            <p className="text-[10px] text-muted-foreground/60 mb-1">
              Last check: {formatTimeAgo(compliance.lastCheck)}
            </p>
            <button
              onClick={() =>
                console.log('[AgentGovernance] View full compliance report')
              }
              className="text-[10px] font-medium text-primary hover:underline cursor-pointer"
            >
              View Report &rarr;
            </button>
          </div>
        </div>
      </motion.div>

      {/* ── 3. Agent cards grid ── */}
      {agents.length === 0 ? (
        <motion.div
          variants={cardVariants}
          className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm"
        >
          <Shield className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">{t('empty.agentGovernance')}</p>
        </motion.div>
      ) : (
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              scopes={getAgentScopes(agent.id, permissions)}
              statusKey={toStatusKey(agent.status)}
            />
          ))}
        </motion.div>
      )}

      {/* ── 4. Permission summary (expandable) ── */}
      <motion.div variants={cardVariants}>
        <PermissionMatrix agents={agents} permissions={permissions} />
      </motion.div>
    </motion.div>
  )
}
