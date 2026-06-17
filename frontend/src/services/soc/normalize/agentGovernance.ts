/**
 * normalizeAgentGovernance — transforms raw API payload into AgentGovernanceView.
 */

// ── View model ──

interface AgentGovernanceView {
  agents: AgentItemView[]
  permissions: PermissionSetView[]
  compliance: ComplianceReportView
}

interface AgentItemView {
  id: string
  name: string
  status: 'active' | 'paused' | 'error'
  lastHeartbeat: string
}

interface PermissionSetView {
  agentId: string
  scopes: string[]
}

interface ComplianceReportView {
  passed: number
  failed: number
  lastCheck: string
}

// ── Normalizer ──

function normalizeAgentGovernance(raw: Record<string, unknown>): AgentGovernanceView {
  if (!raw || typeof raw !== 'object') {
    return { agents: [], permissions: [], compliance: { passed: 0, failed: 0, lastCheck: '' } }
  }
  return {
    agents: (raw.agents as AgentItemView[]) ?? [],
    permissions: (raw.permissions as PermissionSetView[]) ?? [],
    compliance: (raw.compliance as ComplianceReportView) ?? { passed: 0, failed: 0, lastCheck: '' },
  }
}

export { normalizeAgentGovernance }
export type { AgentGovernanceView, AgentItemView, PermissionSetView, ComplianceReportView }
