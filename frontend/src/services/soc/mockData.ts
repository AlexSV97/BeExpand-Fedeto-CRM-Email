/**
 * mockData.ts — Consolidated mock data for all SOC surfaces.
 *
 * When the backend is unreachable, each surface falls back to its
 * matching MOCK_* constant so the UI remains usable for demos and
 * development.
 *
 * ── Maintenance guideline ────────────────────────────────────────────
 * When updating the backend API contracts, update the corresponding
 * mock data here at the same time.
 *
 * ── Supplement exports ───────────────────────────────────────────────
 * Some surfaces render richer UI data than the normaliser view types
 * provide. Those get their own supplementary types and constants.
 */

// ── Imports ───────────────────────────────────────────────────────────────

import { applyNeutralCopy } from '../../content/socCopy'
import type {
  CommandCenterView,
} from './normalize/commandCenter'
import type {
  TicketQueueView,
} from './normalize/ticketQueue'
import type {
  TicketCopilotView,
} from './normalize/ticketCopilot'
import type {
  SlaWarRoomView,
} from './normalize/slaWarRoom'
import type {
  KnowledgeVaultView,
} from './normalize/knowledgeVault'
import type {
  AgentGovernanceView,
} from './normalize/agentGovernance'
import type {
  ReportingView,
} from './normalize/reporting'
import type {
  AuditView,
} from './normalize/audit'
import type {
  ConfigurationView,
} from './normalize/configuration'

// ═════════════════════════════════════════════════════════════════════════
// COMMAND CENTER
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_COMMAND_CENTER: CommandCenterView = {
  kpiCards: [
    { label: 'Active Tickets', value: 1247, trend: 'up', change: 8 },
    { label: 'Open Incidents', value: 23, trend: 'down', change: 12 },
    { label: 'SLA Breaches', value: 3, trend: 'up', change: 50 },
    { label: 'Queue Pressure', value: 68, trend: 'up', change: 5 },
  ],
  recentAlerts: [
    { id: 'alert-1', severity: 'critical', message: 'Circuit timeout on MX-480 edge router', timestamp: '2026-06-17T09:30:00Z' },
    { id: 'alert-2', severity: 'warning', message: 'BGP flap recurrence on peer AS64512', timestamp: '2026-06-17T09:15:00Z' },
    { id: 'alert-3', severity: 'warning', message: 'SSL certificate for *.aiuken.com expires in 7 days', timestamp: '2026-06-17T09:00:00Z' },
    { id: 'alert-4', severity: 'info', message: 'DDoS mitigation drill scheduled for 22:00 UTC', timestamp: '2026-06-17T08:45:00Z' },
    { id: 'alert-5', severity: 'info', message: 'Routine maintenance: SNMP poller upgrade', timestamp: '2026-06-17T08:30:00Z' },
  ],
  queuePressure: 68,
  surfaceStatus: 'operational',
  operatingMode: 'demo',
}

// ── SLA Risk items (supplementary -- rendered below the main grid) ────

export interface SlaRiskItem {
  ticketId: string
  subject: string
  deadline: string
  remainingSeconds: number
}

export const MOCK_SLA_RISKS: SlaRiskItem[] = [
  { ticketId: 'TKT-1024', subject: applyNeutralCopy('Circuit timeout on MX-480'), deadline: '2026-06-17T18:00:00Z', remainingSeconds: 5400 },
  { ticketId: 'TKT-1021', subject: applyNeutralCopy('Lap 5 — BGP flap recurrence'), deadline: '2026-06-17T20:00:00Z', remainingSeconds: 10800 },
  { ticketId: 'TKT-1018', subject: applyNeutralCopy('Garage port security violation'), deadline: '2026-06-18T06:00:00Z', remainingSeconds: 32400 },
]

// ═════════════════════════════════════════════════════════════════════════
// SMART TICKET QUEUE
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_TICKET_QUEUE: TicketQueueView = {
  tickets: [
    { id: 'TKT-1024', subject: 'Circuit timeout on MX-480 edge router', status: 'in_progress', priority: 'critical', assignee: 'Ana López', createdAt: '2026-06-17T08:00:00Z', updatedAt: '2026-06-17T09:30:00Z' },
    { id: 'TKT-1021', subject: 'BGP flap recurrence — Tier-1 ISP peer', status: 'open', priority: 'high', assignee: 'Miguel Torres', createdAt: '2026-06-17T06:30:00Z', updatedAt: '2026-06-17T09:15:00Z' },
    { id: 'TKT-1018', subject: 'Port security violation — access switch', status: 'open', priority: 'medium', assignee: 'Valentina Ortiz', createdAt: '2026-06-17T05:00:00Z', updatedAt: '2026-06-17T09:00:00Z' },
    { id: 'TKT-1015', subject: 'SSL certificate renewal — *.aiuken.com', status: 'resolved', priority: 'low', assignee: 'Sofía Ramírez', createdAt: '2026-06-16T14:00:00Z', updatedAt: '2026-06-17T07:50:00Z' },
    { id: 'TKT-1027', subject: 'DDoS mitigation rule deployment', status: 'open', priority: 'critical', assignee: 'Carlos Ruiz', createdAt: '2026-06-17T09:00:00Z', updatedAt: '2026-06-17T09:20:00Z' },
    { id: 'TKT-1012', subject: 'SNMP poller timeout — core switch stack', status: 'in_progress', priority: 'high', assignee: 'Laura García', createdAt: '2026-06-16T10:00:00Z', updatedAt: '2026-06-17T08:45:00Z' },
    { id: 'TKT-1009', subject: 'Firewall policy audit — PCI DSS scope', status: 'closed', priority: 'medium', assignee: 'Pedro Martínez', createdAt: '2026-06-15T09:00:00Z', updatedAt: '2026-06-16T18:00:00Z' },
    { id: 'TKT-1005', subject: 'WiFi controller firmware upgrade', status: 'resolved', priority: 'low', assignee: 'Diego Fernández', createdAt: '2026-06-14T11:00:00Z', updatedAt: '2026-06-15T14:30:00Z' },
  ],
  total: 8,
  page: 1,
  filters: {
    status: ['open', 'in_progress', 'resolved', 'closed'],
    priority: ['critical', 'high', 'medium', 'low'],
    assignee: ['Ana López', 'Carlos Ruiz', 'Miguel Torres'],
  },
}

// ═════════════════════════════════════════════════════════════════════════
// TICKET COPILOT
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_TICKET_COPILOT: TicketCopilotView = {
  conversation: [
    {
      role: 'system',
      content: applyNeutralCopy('Ticket TKT-1001 opened for circuit latency on MX-480 edge router. Priority: High. Assigned to Network Ops.'),
      timestamp: new Date(Date.now() - 3600000).toISOString(),
    },
    {
      role: 'assistant',
      content: applyNeutralCopy('I\'ve analysed the recent BGP logs for this circuit. There\'s a pattern of route flapping starting around 02:30 UTC. Recommended: check peer AS 64512 for recent config changes.'),
      timestamp: new Date(Date.now() - 1800000).toISOString(),
    },
    {
      role: 'user',
      content: applyNeutralCopy('Confirmed — peer AS64512 had a maintenance window last night. Rolling back the BGP community change.'),
      timestamp: new Date(Date.now() - 600000).toISOString(),
    },
    {
      role: 'assistant',
      content: applyNeutralCopy('Good catch. After rollback, monitor the circuit for 30 min and verify the flap count drops to zero. I\'ll draft the post-mortem summary.'),
      timestamp: new Date(Date.now() - 300000).toISOString(),
    },
  ],
  suggestedActions: [
    { id: 's1', label: applyNeutralCopy('Apply BGP rollback command'), action: 'apply_bgp_rollback' },
    { id: 's2', label: applyNeutralCopy('Draft post-mortem summary'), action: 'draft_post_mortem' },
    { id: 's3', label: applyNeutralCopy('Notify affected customers'), action: 'notify_customers' },
    { id: 's4', label: applyNeutralCopy('Escalate to Tier-3 NOC'), action: 'escalate_tier3' },
  ],
  ticketContext: {
    ticketId: 'TKT-1001',
    subject: applyNeutralCopy('Circuit latency on MX-480 edge router — possible BGP flap'),
    status: 'in_progress',
    priority: 'high',
    articleCount: 3,
  },
}

// ═════════════════════════════════════════════════════════════════════════
// SLA WAR ROOM
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_SLA_WAR_ROOM: SlaWarRoomView = {
  breachTimers: [
    { ticketId: 'TKT-1024', slaName: 'Critical — 1h', remainingSeconds: 1800, status: 'warning' },
    { ticketId: 'TKT-1021', slaName: 'High — 4h', remainingSeconds: 5400, status: 'ok' },
    { ticketId: 'TKT-1027', slaName: 'Critical — 1h', remainingSeconds: -600, status: 'breached' },
  ],
  escalations: [
    { id: 'esc-1', ticketId: 'TKT-1027', level: 2, reason: 'SLA breach — DDoS mitigation', escalatedAt: '2026-06-17T08:15:00Z' },
    { id: 'esc-2', ticketId: 'TKT-1021', level: 1, reason: 'Unresolved after 2h', escalatedAt: '2026-06-16T17:30:00Z' },
  ],
  activeSLAs: [
    { id: 'critical', name: 'Critical', targetSeconds: 3600, activeCount: 2, breachCount: 1 },
    { id: 'high', name: 'High', targetSeconds: 14400, activeCount: 1, breachCount: 0 },
    { id: 'medium', name: 'Medium', targetSeconds: 28800, activeCount: 1, breachCount: 0 },
    { id: 'low', name: 'Low', targetSeconds: 86400, activeCount: 0, breachCount: 0 },
  ],
  operatingMode: 'demo',
}

// ── Rich timer cards (supplementary -- shows countdown with progress) ──

export interface ActiveSlaTimer {
  ticketId: string
  subject: string
  priority: string
  deadline: string
  remainingSeconds: number
  totalSeconds: number
}

export interface BreachAlert {
  id: string
  ticketId: string
  subject: string
  priority: string
  status: 'breached' | 'near-breach'
  timeSinceBreach: string
  escalationLevel: number
  assignedAgent: string
}

export interface PriorityComplianceCell {
  priority: string
  queue: string
  compliance: number
  total: number
  breached: number
}

export const QUEUES = ['Network', 'Security', 'Applications', 'Infrastructure']

export const MOCK_SLA_TIMERS: ActiveSlaTimer[] = [
  { ticketId: 'TKT-1024', subject: 'Circuit timeout on MX-480 edge router', priority: 'critical', deadline: '2026-06-17T18:00:00Z', remainingSeconds: 1800, totalSeconds: 3600 },
  { ticketId: 'TKT-1021', subject: 'BGP flap recurrence — Tier-1 ISP peer', priority: 'high', deadline: '2026-06-17T20:00:00Z', remainingSeconds: 5400, totalSeconds: 14400 },
  { ticketId: 'TKT-1018', subject: 'Port security violation -- access switch', priority: 'medium', deadline: '2026-06-18T06:00:00Z', remainingSeconds: 28800, totalSeconds: 28800 },
  { ticketId: 'TKT-1015', subject: 'SSL certificate renewal -- *.aiuken.com', priority: 'low', deadline: '2026-06-19T12:00:00Z', remainingSeconds: 72000, totalSeconds: 86400 },
  { ticketId: 'TKT-1027', subject: 'DDoS mitigation rule deployment', priority: 'critical', deadline: '2026-06-17T16:30:00Z', remainingSeconds: -600, totalSeconds: 3600 },
]

export const MOCK_SLA_BREACHES: BreachAlert[] = [
  { id: 'br-1', ticketId: 'TKT-1027', subject: 'DDoS mitigation rule deployment', priority: 'critical', status: 'breached', timeSinceBreach: '12 min', escalationLevel: 2, assignedAgent: 'Carlos Ruiz' },
  { id: 'br-2', ticketId: 'TKT-1024', subject: 'Circuit timeout on MX-480 edge router', priority: 'critical', status: 'near-breach', timeSinceBreach: '—', escalationLevel: 1, assignedAgent: 'Ana López' },
  { id: 'br-3', ticketId: 'TKT-1021', subject: 'BGP flap recurrence — Tier-1 ISP peer', priority: 'high', status: 'near-breach', timeSinceBreach: '—', escalationLevel: 0, assignedAgent: 'Miguel Torres' },
]

export const MOCK_SLA_MATRIX: PriorityComplianceCell[] = [
  { priority: 'critical', queue: 'Network', compliance: 78, total: 45, breached: 10 },
  { priority: 'critical', queue: 'Security', compliance: 92, total: 38, breached: 3 },
  { priority: 'critical', queue: 'Applications', compliance: 65, total: 20, breached: 7 },
  { priority: 'critical', queue: 'Infrastructure', compliance: 85, total: 32, breached: 5 },
  { priority: 'high', queue: 'Network', compliance: 82, total: 62, breached: 11 },
  { priority: 'high', queue: 'Security', compliance: 88, total: 55, breached: 7 },
  { priority: 'high', queue: 'Applications', compliance: 73, total: 40, breached: 11 },
  { priority: 'high', queue: 'Infrastructure', compliance: 90, total: 48, breached: 5 },
  { priority: 'medium', queue: 'Network', compliance: 91, total: 80, breached: 7 },
  { priority: 'medium', queue: 'Security', compliance: 95, total: 72, breached: 4 },
  { priority: 'medium', queue: 'Applications', compliance: 87, total: 65, breached: 8 },
  { priority: 'medium', queue: 'Infrastructure', compliance: 93, total: 70, breached: 5 },
  { priority: 'low', queue: 'Network', compliance: 97, total: 120, breached: 4 },
  { priority: 'low', queue: 'Security', compliance: 99, total: 98, breached: 1 },
  { priority: 'low', queue: 'Applications', compliance: 96, total: 110, breached: 4 },
  { priority: 'low', queue: 'Infrastructure', compliance: 98, total: 105, breached: 2 },
]

// ═════════════════════════════════════════════════════════════════════════
// KNOWLEDGE VAULT
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_KNOWLEDGE_VAULT: KnowledgeVaultView = {
  articles: [
    { id: 'KB-001', title: 'BGP Route Flap Mitigation — Standard Operating Procedure', excerpt: 'Step-by-step SOP for identifying and mitigating BGP route flaps across all managed peers.', category: 'Runbooks', tags: ['bgp', 'routing', 'flap', 'mitigation'], updatedAt: '2026-06-15T10:30:00Z' },
    { id: 'KB-002', title: 'DDoS Mitigation Playbook — Layer 3/4 Attacks', excerpt: 'Comprehensive playbook for detecting, classifying, and mitigating volumetric DDoS attacks.', category: 'Runbooks', tags: ['ddos', 'mitigation', 'layer3', 'layer4'], updatedAt: '2026-06-14T08:00:00Z' },
    { id: 'KB-003', title: 'Known Issue: MX-480 Line Card LC-4XGE-XFP Hard Lockup', excerpt: 'Under sustained 90%+ throughput, LC-4XGE-XFP line cards may enter a hard lockup state.', category: 'Operations', tags: ['mx-480', 'line-card', 'lockup', 'hardware'], updatedAt: '2026-06-13T14:15:00Z' },
    { id: 'KB-004', title: 'Release Notes — v3.2.0 Security Policy Engine', excerpt: 'New security policy engine introduces zone-based firewalling and application-layer inspection.', category: 'Security', tags: ['release', 'security', 'policy', 'engine'], updatedAt: '2026-06-12T16:45:00Z' },
    { id: 'KB-005', title: 'SOP: SSL/TLS Certificate Renewal via ACME Automation', excerpt: 'Automated certificate lifecycle management using ACME protocol.', category: 'FAQs', tags: ['ssl', 'tls', 'certificate', 'acme', 'renewal'], updatedAt: '2026-06-11T09:00:00Z' },
  ],
  categories: ['Cases', 'Runbooks', 'FAQs', 'Security', 'Operations'],
  searchSuggestions: ['password reset', 'SLA breach', 'onboarding', 'incident response', 'certificate renewal'],
}

// ── Rich articles with relevance score (supplementary) ────────────────

export interface MockArticle {
  id: string
  title: string
  excerpt: string
  category: string
  tags: string[]
  updatedAt: string
  relevance: number
}

export const MOCK_ARTICLES: MockArticle[] = [
  { id: 'KB-001', title: 'BGP Route Flap Mitigation — Standard Operating Procedure', excerpt: 'Step-by-step SOP for identifying and mitigating BGP route flaps across all managed peers. Covers monitoring, confirmation, rollback, and post-mortem.', category: 'Runbooks', tags: ['bgp', 'routing', 'flap', 'mitigation'], updatedAt: '2026-06-15T10:30:00Z', relevance: 98 },
  { id: 'KB-002', title: 'DDoS Mitigation Playbook — Layer 3/4 Attacks', excerpt: 'Comprehensive playbook for detecting, classifying, and mitigating volumetric DDoS attacks targeting customer-facing infrastructure.', category: 'Runbooks', tags: ['ddos', 'mitigation', 'layer3', 'layer4'], updatedAt: '2026-06-14T08:00:00Z', relevance: 95 },
  { id: 'KB-003', title: 'Known Issue: MX-480 Line Card LC-4XGE-XFP Hard Lockup', excerpt: 'Under sustained 90%+ throughput, LC-4XGE-XFP line cards may enter a hard lockup state requiring manual OIR. Affected firmware versions: 18.2R1-18.4R2.', category: 'Operations', tags: ['mx-480', 'line-card', 'lockup', 'hardware'], updatedAt: '2026-06-13T14:15:00Z', relevance: 91 },
  { id: 'KB-004', title: 'Release Notes — v3.2.0 Security Policy Engine', excerpt: 'New security policy engine introduces zone-based firewalling, application-layer inspection, and TLS 1.3 termination. Backward-compatible config migration.', category: 'Security', tags: ['release', 'security', 'policy', 'engine'], updatedAt: '2026-06-12T16:45:00Z', relevance: 88 },
  { id: 'KB-005', title: 'SOP: SSL/TLS Certificate Renewal via ACME Automation', excerpt: 'Automated certificate lifecycle management using ACME protocol with Let\'s Encrypt and Sectigo. Covers validation, renewal, and revocation workflows.', category: 'FAQs', tags: ['ssl', 'tls', 'certificate', 'acme', 'renewal'], updatedAt: '2026-06-11T09:00:00Z', relevance: 85 },
  { id: 'KB-006', title: 'Incident Response Playbook — Ransomware Detection', excerpt: 'Detection, containment, eradication, and recovery steps for ransomware incidents affecting customer environments. Includes IOC indicators and C2 blocklists.', category: 'Security', tags: ['ransomware', 'incident', 'response', 'security'], updatedAt: '2026-06-10T11:30:00Z', relevance: 92 },
  { id: 'KB-007', title: 'Known Issue: SNMP BulkWalk Timeout on Large OID Trees', excerpt: 'SNMP bulkwalk operations against OID trees exceeding 10,000 nodes may time out after 30s. Workaround: use walk with max-repetitions 25 or split queries.', category: 'Operations', tags: ['snmp', 'bulkwalk', 'timeout', 'monitoring'], updatedAt: '2026-06-09T13:20:00Z', relevance: 78 },
  { id: 'KB-008', title: 'Release Notes — v2.1.0 Log Aggregation Pipeline', excerpt: 'New log aggregation pipeline with Elasticsearch 8.x backend, improved indexing performance, and support for structured syslog over TCP/TLS.', category: 'Cases', tags: ['release', 'logging', 'elasticsearch', 'pipeline'], updatedAt: '2026-06-08T10:00:00Z', relevance: 82 },
]

// ═════════════════════════════════════════════════════════════════════════
// AGENT GOVERNANCE
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_AGENT_GOVERNANCE: AgentGovernanceView = {
  agents: [
    { id: 'ag-1', name: 'Ana López', status: 'active', lastHeartbeat: '2026-06-17T09:15:00Z' },
    { id: 'ag-2', name: 'Carlos Ruiz', status: 'active', lastHeartbeat: '2026-06-17T09:30:00Z' },
    { id: 'ag-3', name: 'Miguel Torres', status: 'active', lastHeartbeat: '2026-06-17T09:20:00Z' },
    { id: 'ag-4', name: 'Laura García', status: 'active', lastHeartbeat: '2026-06-17T08:45:00Z' },
    { id: 'ag-5', name: 'Pedro Martínez', status: 'active', lastHeartbeat: '2026-06-17T09:28:00Z' },
    { id: 'ag-6', name: 'Sofía Ramírez', status: 'paused', lastHeartbeat: '2026-06-16T18:00:00Z' },
    { id: 'ag-7', name: 'Diego Fernández', status: 'active', lastHeartbeat: '2026-06-17T09:25:00Z' },
    { id: 'ag-8', name: 'Valentina Ortiz', status: 'active', lastHeartbeat: '2026-06-17T09:22:00Z' },
  ],
  permissions: [
    { agentId: 'ag-1', scopes: ['tickets:read', 'tickets:write', 'alerts:read'] },
    { agentId: 'ag-2', scopes: ['tickets:read', 'tickets:write', 'alerts:read', 'escalate'] },
    { agentId: 'ag-3', scopes: ['tickets:read', 'alerts:read'] },
  ],
  compliance: { passed: 6, failed: 2, lastCheck: '2026-06-17T08:00:00Z' },
}

// ── Rich agent rows (supplementary -- role, queue, compliance, etc.) ──

export interface AgentRowData {
  id: string
  name: string
  role: string
  status: string
  queue: string
  ticketsToday: number
  complianceScore: number
  lastActive: string
}

export const MOCK_AGENTS_DATA: AgentRowData[] = [
  { id: 'ag-1', name: 'Ana López', role: 'senior', status: 'online', queue: 'Network', ticketsToday: 12, complianceScore: 94, lastActive: '2026-06-17T09:15:00Z' },
  { id: 'ag-2', name: 'Carlos Ruiz', role: 'senior', status: 'busy', queue: 'Security', ticketsToday: 8, complianceScore: 88, lastActive: '2026-06-17T09:30:00Z' },
  { id: 'ag-3', name: 'Miguel Torres', role: 'junior', status: 'online', queue: 'Network', ticketsToday: 15, complianceScore: 76, lastActive: '2026-06-17T09:20:00Z' },
  { id: 'ag-4', name: 'Laura García', role: 'junior', status: 'idle', queue: 'Applications', ticketsToday: 6, complianceScore: 92, lastActive: '2026-06-17T08:45:00Z' },
  { id: 'ag-5', name: 'Pedro Martínez', role: 'supervisor', status: 'online', queue: '—', ticketsToday: 3, complianceScore: 100, lastActive: '2026-06-17T09:28:00Z' },
  { id: 'ag-6', name: 'Sofía Ramírez', role: 'senior', status: 'offline', queue: 'Infrastructure', ticketsToday: 0, complianceScore: 91, lastActive: '2026-06-16T18:00:00Z' },
  { id: 'ag-7', name: 'Diego Fernández', role: 'junior', status: 'busy', queue: 'Security', ticketsToday: 10, complianceScore: 71, lastActive: '2026-06-17T09:25:00Z' },
  { id: 'ag-8', name: 'Valentina Ortiz', role: 'junior', status: 'online', queue: 'Applications', ticketsToday: 9, complianceScore: 83, lastActive: '2026-06-17T09:22:00Z' },
]

// ═════════════════════════════════════════════════════════════════════════
// REPORTING
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_REPORTING: ReportingView = {
  metrics: [
    { label: 'Overall Compliance', value: 86.2, unit: '%' },
    { label: 'Total Tickets', value: 1284 },
    { label: 'Breached', value: 42 },
    { label: 'Active Agents', value: 6 },
  ],
  trends: [
    { date: '2026-06-10', value: 45, metric: 'tickets' },
    { date: '2026-06-11', value: 52, metric: 'tickets' },
    { date: '2026-06-12', value: 38, metric: 'tickets' },
    { date: '2026-06-13', value: 61, metric: 'tickets' },
    { date: '2026-06-14', value: 47, metric: 'tickets' },
    { date: '2026-06-15', value: 22, metric: 'tickets' },
    { date: '2026-06-16', value: 18, metric: 'tickets' },
  ],
  reportTypes: ['slaCompliance', 'agentPerformance', 'ticketVolume', 'queueTrends'],
  operatingMode: 'demo',
}

// ── Chart data for report types (supplementary) ──────────────────────

export interface ChartDataPoint {
  name: string
  value: number
  secondary?: number
}

export interface MockReportData {
  title: string
  icon: string
  data: ChartDataPoint[]
  metrics: { label: string; value: string | number; icon: string }[]
}

export const MOCK_REPORTS_DATA: Record<string, MockReportData> = {
  slaCompliance: {
    title: 'SLA Compliance',
    icon: 'CheckCircle',
    data: [
      { name: 'Network', value: 87 },
      { name: 'Security', value: 93 },
      { name: 'Applications', value: 82 },
      { name: 'Infrastructure', value: 91 },
      { name: 'Cloud', value: 78 },
    ],
    metrics: [
      { label: 'Overall Compliance', value: '86.2%', icon: 'CheckCircle' },
      { label: 'Total Tickets', value: '1,284', icon: 'FileText' },
      { label: 'Breached', value: '42', icon: 'Clock' },
    ],
  },
  agentPerformance: {
    title: 'Agent Performance',
    icon: 'Users',
    data: [
      { name: 'Ana L.', value: 94, secondary: 12 },
      { name: 'Carlos R.', value: 88, secondary: 8 },
      { name: 'Miguel T.', value: 76, secondary: 15 },
      { name: 'Laura G.', value: 92, secondary: 6 },
      { name: 'Diego F.', value: 71, secondary: 10 },
      { name: 'Valentina O.', value: 83, secondary: 9 },
    ],
    metrics: [
      { label: 'Avg Compliance', value: '84.0%', icon: 'TrendingUp' },
      { label: 'Active Agents', value: '6', icon: 'Users' },
      { label: 'Total Tickets', value: '60', icon: 'FileText' },
    ],
  },
  ticketVolume: {
    title: 'Ticket Volume',
    icon: 'BarChart3',
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
      { label: 'Total Tickets', value: '284', icon: 'FileText' },
      { label: 'Daily Avg', value: '40.6', icon: 'BarChart3' },
      { label: 'Peak Day', value: 'Thu (61)', icon: 'TrendingUp' },
    ],
  },
  queueTrends: {
    title: 'Queue Trends',
    icon: 'LineChart',
    data: [
      { name: 'Week 1', value: 45, secondary: 38 },
      { name: 'Week 2', value: 52, secondary: 42 },
      { name: 'Week 3', value: 38, secondary: 35 },
      { name: 'Week 4', value: 61, secondary: 48 },
    ],
    metrics: [
      { label: 'Total Tickets', value: '196', icon: 'FileText' },
      { label: 'Avg Resolution', value: '4.2h', icon: 'Clock' },
      { label: 'SLA Compliance', value: '87%', icon: 'CheckCircle' },
    ],
  },
}

// ═════════════════════════════════════════════════════════════════════════
// AUDIT
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_AUDIT: AuditView = {
  events: [
    { id: 'evt-1', actor: 'Ana López', action: 'ticket.updated', target: 'TKT-1024', timestamp: '2026-06-17T09:30:00Z', details: { change: 'Priority changed from high to critical' } },
    { id: 'evt-2', actor: 'Carlos Ruiz', action: 'ticket.escalated', target: 'TKT-1027', timestamp: '2026-06-17T09:00:00Z', details: { note: 'Escalated to Level 2 — SLA breach' } },
    { id: 'evt-3', actor: 'System', action: 'agent.status_changed', target: 'ag-6', timestamp: '2026-06-17T08:45:00Z', details: { message: 'Agent Sofía Ramírez auto-paused after 30 min inactivity' } },
    { id: 'evt-4', actor: 'System', action: 'sla.breach', target: 'TKT-1027', timestamp: '2026-06-17T08:15:00Z', details: { message: 'Critical SLA breached — DDoS mitigation beyond 1h window' } },
    { id: 'evt-5', actor: 'Pedro Martínez', action: 'config.updated', target: 'sla-policy', timestamp: '2026-06-17T07:30:00Z', details: { change: 'SLA policy updated: Critical grace period reduced to 30 min' } },
    { id: 'evt-6', actor: 'Laura García', action: 'kb.article.created', target: 'KB-009', timestamp: '2026-06-17T07:00:00Z', details: { title: 'Circuit Mitigation Runbook v2' } },
  ],
  actors: ['Ana López', 'Carlos Ruiz', 'Miguel Torres', 'Laura García', 'Pedro Martínez', 'Sofía Ramírez', 'Diego Fernández', 'Valentina Ortiz'],
  timeRange: { from: '2026-06-10T00:00:00Z', to: '2026-06-17T09:30:00Z' },
}

export interface AuditChartDataPoint {
  name: string
  tickets: number
  security: number
  config: number
}

export const MOCK_AUDIT_CHART: AuditChartDataPoint[] = [
  { name: 'Mon', tickets: 12, security: 8, config: 3 },
  { name: 'Tue', tickets: 18, security: 5, config: 6 },
  { name: 'Wed', tickets: 10, security: 12, config: 2 },
  { name: 'Thu', tickets: 22, security: 7, config: 8 },
  { name: 'Fri', tickets: 15, security: 9, config: 4 },
  { name: 'Sat', tickets: 6, security: 4, config: 1 },
  { name: 'Sun', tickets: 4, security: 3, config: 0 },
]

export const MOCK_AUDIT_SUMMARY = {
  totalEvents: 1284,
  uniqueAgents: 8,
  uniqueActions: 12,
  period: { from: '2026-06-10T00:00:00Z', to: '2026-06-17T09:30:00Z' },
}

// ═════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═════════════════════════════════════════════════════════════════════════

export const MOCK_CONFIGURATION: ConfigurationView = {
  settings: [
    { key: 'org_name', value: 'Aiuken CRM', type: 'string' },
    { key: 'soc_name', value: 'Aiuken SOC-NOC', type: 'string' },
    { key: 'timezone', value: 'America/Argentina/Buenos_Aires', type: 'string' },
    { key: 'language', value: 'es-AR', type: 'string' },
    { key: 'critical_seconds', value: 3600, type: 'number' },
    { key: 'high_seconds', value: 14400, type: 'number' },
    { key: 'medium_seconds', value: 28800, type: 'number' },
    { key: 'low_seconds', value: 86400, type: 'number' },
    { key: 'auto_pause_min', value: 15, type: 'number' },
    { key: 'escalation_delay_min', value: 5, type: 'number' },
    { key: 'email_enabled', value: true, type: 'boolean' },
    { key: 'slack_enabled', value: true, type: 'boolean' },
    { key: 'webhook_url', value: 'https://hooks.aiuken.com/soc/alerts', type: 'string' },
  ],
  thresholds: [
    { name: 'Critical SLA', warning: 1800, critical: 600 },
    { name: 'High SLA', warning: 7200, critical: 3600 },
    { name: 'Medium SLA', warning: 14400, critical: 7200 },
    { name: 'Low SLA', warning: 43200, critical: 21600 },
  ],
  featureFlags: [
    { key: 'auto_escalation', enabled: true, description: 'Enable automatic escalation on SLA breach' },
    { key: 'ai_suggestions', enabled: true, description: 'Show AI-powered suggested actions' },
    { key: 'dark_mode', enabled: false, description: 'Enable dark mode UI' },
  ],
}

// ═════════════════════════════════════════════════════════════════════════
// MOCK DATA REGISTRY — maps each endpoint to its mock data and surface
// ═════════════════════════════════════════════════════════════════════════

import { SOC_ENDPOINTS } from './endpoints'
import { SURFACE_IDS } from './contracts'
import type { SurfaceId } from './contracts'

/**
 * Registry entry linking an endpoint to its mock data and the surface
 * that consumes it. The surface ID is used to update the dataSource
 * store when the hook falls back to mock data.
 */
export interface MockRegistryEntry<T = unknown> {
  endpoint: string
  surfaceId: SurfaceId
  mockData: T
}

/**
 * Every SOC surface endpoint -> mock data mapping.
 * Add new entries here when surfaces grow.
 */
export const MOCK_DATA_REGISTRY: MockRegistryEntry[] = [
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.COMMAND_CENTER],
    surfaceId: SURFACE_IDS.COMMAND_CENTER,
    mockData: MOCK_COMMAND_CENTER,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.SMART_TICKET_QUEUE],
    surfaceId: SURFACE_IDS.SMART_TICKET_QUEUE,
    mockData: MOCK_TICKET_QUEUE,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.TICKET_COPILOT],
    surfaceId: SURFACE_IDS.TICKET_COPILOT,
    mockData: MOCK_TICKET_COPILOT,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.SLA_WAR_ROOM],
    surfaceId: SURFACE_IDS.SLA_WAR_ROOM,
    mockData: MOCK_SLA_WAR_ROOM,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.KNOWLEDGE_VAULT],
    surfaceId: SURFACE_IDS.KNOWLEDGE_VAULT,
    mockData: MOCK_KNOWLEDGE_VAULT,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.AGENT_GOVERNANCE],
    surfaceId: SURFACE_IDS.AGENT_GOVERNANCE,
    mockData: MOCK_AGENT_GOVERNANCE,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.REPORTING],
    surfaceId: SURFACE_IDS.REPORTING,
    mockData: MOCK_REPORTING,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.AUDIT],
    surfaceId: SURFACE_IDS.AUDIT,
    mockData: MOCK_AUDIT,
  },
  {
    endpoint: SOC_ENDPOINTS[SURFACE_IDS.CONFIGURATION],
    surfaceId: SURFACE_IDS.CONFIGURATION,
    mockData: MOCK_CONFIGURATION,
  },
]
