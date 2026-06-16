import React, { type ComponentType, type LazyExoticComponent } from 'react'
import { Shield, Ticket, Bot, Gauge, BookOpen, UserCheck, BarChart3, ScrollText, Settings } from 'lucide-react'
import { SURFACE_IDS, type SurfaceDescriptor, type SurfaceId } from './contracts'

// ── Lazy imports for surface page components ──
// Placeholder pages exist at these paths; Phase 3/4 will replace them with real implementations.

function lazyPage(importFn: () => Promise<{ default: ComponentType }>): LazyExoticComponent<ComponentType> {
  return React.lazy(importFn)
}

const CommandCenterSurface = lazyPage(() => import('../../pages/soc/CommandCenterSurface'))
const SmartTicketQueueSurface = lazyPage(() => import('../../pages/soc/SmartTicketQueueSurface'))
const TicketCopilotSurface = lazyPage(() => import('../../pages/soc/TicketCopilotSurface'))
const SlaWarRoomSurface = lazyPage(() => import('../../pages/soc/SlaWarRoomSurface'))
const KnowledgeVaultSurface = lazyPage(() => import('../../pages/soc/KnowledgeVaultSurface'))
const AgentGovernanceSurface = lazyPage(() => import('../../pages/soc/AgentGovernanceSurface'))
const ReportingSurface = lazyPage(() => import('../../pages/soc/ReportingSurface'))
const AuditSurface = lazyPage(() => import('../../pages/soc/AuditSurface'))
const ConfigurationSurface = lazyPage(() => import('../../pages/soc/ConfigurationSurface'))

// ── Default surface descriptors ──

const DEFAULT_SURFACES: SurfaceDescriptor[] = [
  // Phase 1
  {
    id: SURFACE_IDS.COMMAND_CENTER,
    label: 'Command Center',
    icon: <Shield className="h-4 w-4" />,
    phase: 1,
    enabled: true,
    component: CommandCenterSurface,
  },
  {
    id: SURFACE_IDS.SMART_TICKET_QUEUE,
    label: 'Smart Ticket Queue',
    icon: <Ticket className="h-4 w-4" />,
    phase: 1,
    enabled: true,
    component: SmartTicketQueueSurface,
  },
  {
    id: SURFACE_IDS.TICKET_COPILOT,
    label: 'Ticket Copilot',
    icon: <Bot className="h-4 w-4" />,
    phase: 1,
    enabled: true,
    component: TicketCopilotSurface,
  },
  // Phase 2
  {
    id: SURFACE_IDS.SLA_WAR_ROOM,
    label: 'SLA War Room',
    icon: <Gauge className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: SlaWarRoomSurface,
  },
  {
    id: SURFACE_IDS.KNOWLEDGE_VAULT,
    label: 'Knowledge Vault',
    icon: <BookOpen className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: KnowledgeVaultSurface,
  },
  {
    id: SURFACE_IDS.AGENT_GOVERNANCE,
    label: 'Agent Governance',
    icon: <UserCheck className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: AgentGovernanceSurface,
  },
  {
    id: SURFACE_IDS.REPORTING,
    label: 'Reporting',
    icon: <BarChart3 className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: ReportingSurface,
  },
  {
    id: SURFACE_IDS.AUDIT,
    label: 'Audit',
    icon: <ScrollText className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: AuditSurface,
  },
  {
    id: SURFACE_IDS.CONFIGURATION,
    label: 'Configuration',
    icon: <Settings className="h-4 w-4" />,
    phase: 2,
    enabled: true,
    component: ConfigurationSurface,
  },
]

// ── Singleton registry instance ──

interface SurfaceRegistry {
  getAll(): SurfaceDescriptor[]
  getByPhase(phase: 1 | 2): SurfaceDescriptor[]
  get(id: SurfaceId): SurfaceDescriptor | undefined
  register(descriptor: SurfaceDescriptor): void
}

let instance: SurfaceRegistry | null = null

export function createSurfaceRegistry(): SurfaceRegistry {
  if (instance) return instance

  const surfaces: Map<SurfaceId, SurfaceDescriptor> = new Map(
    DEFAULT_SURFACES.map((s) => [s.id, s]),
  )

  instance = {
    getAll(): SurfaceDescriptor[] {
      return Array.from(surfaces.values())
    },

    getByPhase(phase: 1 | 2): SurfaceDescriptor[] {
      return Array.from(surfaces.values()).filter((s) => s.phase === phase)
    },

    get(id: SurfaceId): SurfaceDescriptor | undefined {
      return surfaces.get(id)
    },

    register(descriptor: SurfaceDescriptor): void {
      surfaces.set(descriptor.id, descriptor)
    },
  }

  return instance
}

// Pre-initialized singleton for direct import
const surfaceRegistry = createSurfaceRegistry()

export { surfaceRegistry }
export type { SurfaceRegistry }
