/**
 * SOC endpoints and API contracts.
 *
 * Maps surface IDs to API paths and defines initial request/response types
 * for each endpoint.  Types are kept simple and can be refined as backends
 * stabilise.
 */

import { SURFACE_IDS, type SurfaceId } from './contracts'

// ── Endpoint paths ──

const SOC_ENDPOINTS: Record<SurfaceId, string> = {
  [SURFACE_IDS.COMMAND_CENTER]: '/api/v1/soc/command-center',
  [SURFACE_IDS.SMART_TICKET_QUEUE]: '/api/v1/soc/tickets',
  [SURFACE_IDS.TICKET_COPILOT]: '/api/v1/soc/tickets/:id/copilot',
  [SURFACE_IDS.SLA_WAR_ROOM]: '/api/v1/soc/sla',
  [SURFACE_IDS.KNOWLEDGE_VAULT]: '/api/v1/soc/knowledge',
  [SURFACE_IDS.AGENT_GOVERNANCE]: '/api/v1/soc/agents',
  [SURFACE_IDS.REPORTING]: '/api/v1/soc/reports',
  [SURFACE_IDS.AUDIT]: '/api/v1/soc/audit',
  [SURFACE_IDS.CONFIGURATION]: '/api/v1/soc/config',
}

// ── Request / Response types ──

/* ─── Command Center ─── */

interface CommandCenterRequest {
  period?: '24h' | '7d' | '30d'
}

interface CommandCenterResponse {
  kpiCards: CommandCenterKpiCard[]
  recentAlerts: AlertItem[]
  queuePressure: number
  surfaceStatus: string
}

interface CommandCenterKpiCard {
  label: string
  value: number
  trend: 'up' | 'down' | 'stable'
  change?: number
}

interface AlertItem {
  id: string
  severity: 'critical' | 'warning' | 'info'
  message: string
  timestamp: string
}

/* ─── Ticket Queue ─── */

interface TicketQueueRequest {
  page?: number
  limit?: number
  status?: string
  priority?: string
  search?: string
}

interface TicketQueueResponse {
  tickets: TicketItem[]
  total: number
  page: number
  filters: TicketFilters
}

interface TicketItem {
  id: string
  subject: string
  status: string
  priority: string
  assignee?: string
  createdAt: string
  updatedAt: string
}

interface TicketFilters {
  status?: string[]
  priority?: string[]
  assignee?: string[]
}

/* ─── Ticket Copilot ─── */

interface TicketCopilotRequest {
  message?: string
  action?: string
}

interface TicketCopilotResponse {
  conversation: CopilotMessage[]
  suggestedActions: SuggestionItem[]
  ticketContext: TicketContext
}

interface CopilotMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

interface SuggestionItem {
  id: string
  label: string
  action: string
}

interface TicketContext {
  ticketId: string
  subject: string
  status: string
}

/* ─── SLA War Room ─── */

interface SlaWarRoomRequest {
  surfaceId?: string
}

interface SlaWarRoomResponse {
  breachTimers: BreachTimer[]
  escalations: EscalationItem[]
  activeSLAs: SlaItem[]
}

interface BreachTimer {
  ticketId: string
  slaName: string
  remainingSeconds: number
  status: 'ok' | 'warning' | 'breached'
}

interface EscalationItem {
  id: string
  ticketId: string
  level: number
  reason: string
  escalatedAt: string
}

interface SlaItem {
  id: string
  name: string
  targetSeconds: number
  activeCount: number
  breachCount: number
}

/* ─── Knowledge Vault ─── */

interface KnowledgeVaultRequest {
  search?: string
  category?: string
}

interface KnowledgeVaultResponse {
  articles: KnowledgeArticle[]
  categories: string[]
  searchSuggestions: string[]
}

interface KnowledgeArticle {
  id: string
  title: string
  excerpt: string
  category: string
  tags: string[]
  updatedAt: string
}

/* ─── Agent Governance ─── */

interface AgentGovernanceRequest {
  status?: string
}

interface AgentGovernanceResponse {
  agents: AgentItem[]
  permissions: PermissionSet[]
  compliance: ComplianceReport
}

interface AgentItem {
  id: string
  name: string
  status: 'active' | 'paused' | 'error'
  lastHeartbeat: string
}

interface PermissionSet {
  agentId: string
  scopes: string[]
}

interface ComplianceReport {
  passed: number
  failed: number
  lastCheck: string
}

/* ─── Reporting ─── */

interface ReportingRequest {
  reportType?: string
  dateFrom?: string
  dateTo?: string
}

interface ReportingResponse {
  metrics: MetricItem[]
  trends: TrendItem[]
  reportTypes: string[]
}

interface MetricItem {
  label: string
  value: number
  unit?: string
}

interface TrendItem {
  date: string
  value: number
  metric: string
}

/* ─── Audit ─── */

interface AuditRequest {
  actor?: string
  eventType?: string
  from?: string
  to?: string
  page?: number
  limit?: number
}

interface AuditResponse {
  events: AuditEvent[]
  actors: string[]
  timeRange: { from: string; to: string }
}

interface AuditEvent {
  id: string
  actor: string
  action: string
  target: string
  timestamp: string
  details?: Record<string, unknown>
}

/* ─── Configuration ─── */

interface ConfigurationRequest {
  section?: string
}

interface ConfigurationResponse {
  settings: ConfigSetting[]
  thresholds: ConfigThreshold[]
  featureFlags: FeatureFlag[]
}

interface ConfigSetting {
  key: string
  value: unknown
  type: 'string' | 'number' | 'boolean' | 'json'
}

interface ConfigThreshold {
  name: string
  warning: number
  critical: number
}

interface FeatureFlag {
  key: string
  enabled: boolean
  description?: string
}

export { SOC_ENDPOINTS }
export type {
  // Common
  AlertItem,
  // Command Center
  CommandCenterRequest,
  CommandCenterResponse,
  CommandCenterKpiCard,
  // Ticket Queue
  TicketQueueRequest,
  TicketQueueResponse,
  TicketItem,
  TicketFilters,
  // Ticket Copilot
  TicketCopilotRequest,
  TicketCopilotResponse,
  CopilotMessage,
  SuggestionItem,
  TicketContext,
  // SLA War Room
  SlaWarRoomRequest,
  SlaWarRoomResponse,
  BreachTimer,
  EscalationItem,
  SlaItem,
  // Knowledge Vault
  KnowledgeVaultRequest,
  KnowledgeVaultResponse,
  KnowledgeArticle,
  // Agent Governance
  AgentGovernanceRequest,
  AgentGovernanceResponse,
  AgentItem,
  PermissionSet,
  ComplianceReport,
  // Reporting
  ReportingRequest,
  ReportingResponse,
  MetricItem,
  TrendItem,
  // Audit
  AuditRequest,
  AuditResponse,
  AuditEvent,
  // Configuration
  ConfigurationRequest,
  ConfigurationResponse,
  ConfigSetting,
  ConfigThreshold,
  FeatureFlag,
}
