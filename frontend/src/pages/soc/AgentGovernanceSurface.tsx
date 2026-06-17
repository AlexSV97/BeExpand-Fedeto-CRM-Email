/**
 * AgentGovernanceSurface — agent roster and governance dashboard.
 *
 * Shows an agent table with status, role, queue, tickets handled,
 * compliance score, and last active.  Includes role filter, override
 * controls, and a top-level compliance summary bar.
 */

import { useState, useMemo } from 'react'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeAgentGovernance } from '../../services/soc/normalize/agentGovernance'
import { MOCK_AGENT_GOVERNANCE, MOCK_AGENTS_DATA } from '../../services/soc/mockData'
import type { AgentRowData } from '../../services/soc/mockData'
import { SocLoadingState, SocEmptyState, SocErrorState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Users,
  AlertTriangle,
  MoreVertical,
  Activity,
  BarChart3,
  Filter,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.AGENT_GOVERNANCE

const ROLES = ['all', 'senior', 'junior', 'supervisor'] as const

// ─── Helpers ──────────────────────────────────────────────────────────────

function statusDotColor(status: string): string {
  switch (status) {
    case 'online':
      return 'bg-success'
    case 'busy':
      return 'bg-warning'
    case 'idle':
      return 'bg-muted-foreground'
    case 'offline':
      return 'bg-muted'
    default:
      return 'bg-muted'
  }
}

function statusLabel(status: string): string {
  return t(`agent.status.${status}`)
}

function complianceColor(score: number): string {
  if (score >= 90) return 'text-success'
  if (score >= 80) return 'text-chart-1'
  return 'text-destructive'
}

function complianceBg(score: number): string {
  if (score >= 90) return 'bg-success/10'
  if (score >= 80) return 'bg-chart-1/10'
  return 'bg-destructive/10'
}

function roleLabel(role: string): string {
  return t(`agent.role.${role}`)
}

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

// ─── Sub-components ───────────────────────────────────────────────────────

function OverrideMenu({ agentId }: { agentId: string }) {
  const [open, setOpen] = useState(false)

  const actions = [
    { label: t('agent.setAway'), action: 'set_away' },
    { label: t('agent.assignQueue'), action: 'assign_queue' },
    { label: t('agent.overridePermissions'), action: 'override_permissions' },
  ]

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 w-48 bg-card border border-border/50 rounded-xl shadow-lg py-1">
            {actions.map((action) => (
              <button
                key={action.action}
                onClick={() => {
                  console.log(`[AgentGovernance] Override ${action.action} for ${agentId}`)
                  setOpen(false)
                }}
                className="w-full text-left px-4 py-2 text-xs text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
              >
                {action.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function AgentGovernanceSurface() {
  const { data, loading, error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.AGENT_GOVERNANCE],
    normalizeAgentGovernance,
    MOCK_AGENT_GOVERNANCE,
    SURFACE_ID,
  )

  // UI state
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [agents] = useState<AgentRowData[]>(MOCK_AGENTS_DATA)

  // ── Derived ──
  const filteredAgents = useMemo(() => {
    if (roleFilter === 'all') return agents
    return agents.filter((a) => a.role === roleFilter)
  }, [agents, roleFilter])

  const overallCompliance = useMemo(() => {
    if (agents.length === 0) return 100
    const total = agents.reduce((sum, a) => sum + a.complianceScore, 0)
    return Math.round(total / agents.length)
  }, [agents])

  const agentsAtRisk = useMemo(() => {
    return agents.filter((a) => a.complianceScore < 80).length
  }, [agents])

  const isDemo = source === 'mock'

  // ── Loading ──
  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.agentGovernance')} />
  }

  // ── Error ──
  if (error) {
    const socErr: SocError = { code: 'FETCH_ERROR', message: error, retry: refresh }
    return <SocErrorState error={socErr} />
  }

  // ── Empty (only when source is backend and data is empty) ──
  if (source === 'backend' && data.agents.length === 0 && agents.length === 0) {
    return <SocEmptyState surfaceId={SURFACE_ID} />
  }

  // ── Content ──
  return (
    <div className="space-y-4">
      {/* Header + demo badge */}
      <div className="flex items-center gap-2">
        <Users className="h-5 w-5 text-chart-3" />
        <h2 className="text-lg font-semibold">{t('surfaces.agentGovernance')}</h2>
        <span className="text-xs text-muted-foreground">
          ({agents.length} {t('agent.agents')})
        </span>
        {isDemo && (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
            <AlertTriangle className="h-3.5 w-3.5" />
            {"Demo"}
          </div>
        )}
      </div>

      {/* Compliance summary bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
            <BarChart3 className="h-3.5 w-3.5" />
            <span>{t('agent.overallCompliance')}</span>
          </div>
          <p className={cn('text-2xl font-bold', complianceColor(overallCompliance))}>
            {overallCompliance}%
          </p>
        </div>
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
            <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
            <span>{t('agent.agentsAtRisk')}</span>
          </div>
          <p className="text-2xl font-bold text-destructive">
            {agentsAtRisk}
          </p>
        </div>
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
            <Activity className="h-3.5 w-3.5 text-success" />
            <span>{t('agent.currentlyActive')}</span>
          </div>
          <p className="text-2xl font-bold text-success">
            {agents.filter((a) => a.status === 'online' || a.status === 'busy').length}
          </p>
        </div>
      </div>

      {/* Role filter */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mr-1">
          {t('agent.roleLabel')}:
        </span>
        {ROLES.map((role) => (
          <button
            key={role}
            onClick={() => setRoleFilter(role === 'all' ? 'all' : role)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors cursor-pointer',
              roleFilter === role
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border/50 hover:border-border hover:text-foreground',
            )}
          >
            {role === 'all' ? t('agent.role.all') : roleLabel(role)}
          </button>
        ))}
      </div>

      {/* Agent table */}
      {filteredAgents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground bg-card rounded-2xl border border-border/50 shadow-sm">
          <Filter className="h-10 w-10 mb-3 text-muted-foreground/40" />
          <p className="text-sm">{t('empty.agentGovernance')}</p>
        </div>
      ) : (
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
          <div className="hidden md:flex items-center gap-3 px-4 py-3 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b border-border/20 bg-muted/30">
            <span className="flex-1">{t('agent.name')}</span>
            <span className="w-20 text-center">{t('agent.roleCol')}</span>
            <span className="w-20 text-center">{t('agent.statusCol')}</span>
            <span className="w-24 text-center">{t('agent.queue')}</span>
            <span className="w-24 text-center">{t('agent.ticketsToday')}</span>
            <span className="w-20 text-center">{t('agent.compliance')}</span>
            <span className="w-28">{t('agent.lastActive')}</span>
            <span className="w-10" />
          </div>

          <div className="divide-y divide-border/30">
            {filteredAgents.map((agent) => (
              <div key={agent.id} className="flex flex-col md:flex-row items-start md:items-center gap-2 md:gap-3 px-4 py-3 hover:bg-muted/50 transition-colors">
                <div className="flex md:hidden items-center gap-2 w-full">
                  <div className={cn('w-2 h-2 rounded-full', statusDotColor(agent.status))} />
                  <span className="text-sm font-medium text-foreground">{agent.name}</span>
                  <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded border ml-auto', complianceBg(agent.complianceScore))}>
                    {agent.complianceScore}%
                  </span>
                </div>

                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <div className={cn('w-2 h-2 rounded-full shrink-0 hidden md:block', statusDotColor(agent.status))} />
                  <span className="text-sm font-medium text-foreground truncate">{agent.name}</span>
                </div>

                <span className="text-xs text-muted-foreground w-20 shrink-0 text-center">
                  {roleLabel(agent.role)}
                </span>

                <span className="text-[10px] font-medium px-2 py-0.5 rounded border w-20 shrink-0 text-center hidden md:block bg-muted/50 text-muted-foreground border-border/50">
                  {statusLabel(agent.status)}
                </span>

                <span className="text-xs text-muted-foreground w-24 shrink-0 text-center truncate">
                  {agent.queue}
                </span>

                <span className="text-xs text-foreground font-medium w-24 shrink-0 text-center">
                  {agent.ticketsToday}
                </span>

                <span className={cn('text-xs font-medium w-20 shrink-0 text-center', complianceColor(agent.complianceScore))}>
                  {agent.complianceScore}%
                </span>

                <span className="text-xs text-muted-foreground w-28 shrink-0 truncate">
                  {formatTimeAgo(agent.lastActive)}
                </span>

                <div className="shrink-0">
                  <OverrideMenu agentId={agent.id} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

