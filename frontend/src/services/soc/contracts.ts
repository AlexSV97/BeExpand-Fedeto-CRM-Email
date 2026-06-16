import type { ComponentType, LazyExoticComponent, ReactNode } from 'react'

// --- SurfaceId: const-object pattern (single source of truth) ---

const SURFACE_IDS = {
  COMMAND_CENTER: 'commandCenter',
  SMART_TICKET_QUEUE: 'smartTicketQueue',
  TICKET_COPILOT: 'ticketCopilot',
  SLA_WAR_ROOM: 'slaWarRoom',
  KNOWLEDGE_VAULT: 'knowledgeVault',
  AGENT_GOVERNANCE: 'agentGovernance',
  REPORTING: 'reporting',
  AUDIT: 'audit',
  CONFIGURATION: 'configuration',
} as const

type SurfaceId = (typeof SURFACE_IDS)[keyof typeof SURFACE_IDS]

// --- SurfaceDescriptor ---

interface SurfaceDescriptor {
  id: SurfaceId
  label: string
  icon: ReactNode
  phase: 1 | 2
  enabled: boolean
  component: LazyExoticComponent<ComponentType>
}

// --- SocShellConfig ---

interface SocShellConfig {
  enabled: boolean
  activeSurfaceId: SurfaceId
  surfaces: SurfaceDescriptor[]
}

// --- SurfaceStatus ---

type SurfaceStatus = 'loading' | 'ready' | 'error' | 'stale'

// --- SocError ---

interface SocError {
  code: string
  message: string
  retry?: () => void
}

export { SURFACE_IDS }
export type { SurfaceId, SurfaceDescriptor, SocShellConfig, SurfaceStatus, SocError }
