/**
 * normalizeCommandCenter — transforms raw API payload into CommandCenterView.
 */

// ── View model ──

interface CommandCenterView {
  kpiCards: CommandCenterKpiCardView[]
  recentAlerts: AlertItemView[]
  queuePressure: number
  surfaceStatus: string
  operatingMode: string
}

interface CommandCenterKpiCardView {
  label: string
  value: number
  trend: 'up' | 'down' | 'stable'
  change?: number
}

interface AlertItemView {
  id: string
  severity: 'critical' | 'warning' | 'info'
  message: string
  timestamp: string
}

// ── Normalizer ──

function normalizeCommandCenter(raw: Record<string, unknown>): CommandCenterView {
  if (!raw || typeof raw !== 'object') {
    return { kpiCards: [], recentAlerts: [], queuePressure: 0, surfaceStatus: 'error', operatingMode: 'demo' }
  }
  return {
    kpiCards: (raw.kpiCards as CommandCenterKpiCardView[]) ?? [],
    recentAlerts: (raw.recentAlerts as AlertItemView[]) ?? [],
    queuePressure: (raw.queuePressure as number) ?? 0,
    surfaceStatus: (raw.surfaceStatus as string) ?? 'unknown',
    operatingMode: (raw.operatingMode as string) ?? 'demo',
  }
}

export { normalizeCommandCenter }
export type { CommandCenterView, CommandCenterKpiCardView, AlertItemView }
