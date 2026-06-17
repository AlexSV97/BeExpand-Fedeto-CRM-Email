/**
 * normalizeReporting — transforms raw API payload into ReportingView.
 */

// ── View model ──

interface ReportingView {
  metrics: MetricItemView[]
  trends: TrendItemView[]
  reportTypes: string[]
  operatingMode: string
}

interface MetricItemView {
  label: string
  value: number
  unit?: string
}

interface TrendItemView {
  date: string
  value: number
  metric: string
}

// ── Normalizer ──

function normalizeReporting(raw: Record<string, unknown>): ReportingView {
  if (!raw || typeof raw !== 'object') {
    return { metrics: [], trends: [], reportTypes: [], operatingMode: 'demo' }
  }
  return {
    metrics: (raw.metrics as MetricItemView[]) ?? [],
    trends: (raw.trends as TrendItemView[]) ?? [],
    reportTypes: (raw.reportTypes as string[]) ?? [],
    operatingMode: (raw.operatingMode as string) ?? 'demo',
  }
}

export { normalizeReporting }
export type { ReportingView, MetricItemView, TrendItemView }
