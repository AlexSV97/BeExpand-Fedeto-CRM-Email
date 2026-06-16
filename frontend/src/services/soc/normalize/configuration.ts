/**
 * normalizeConfiguration — transforms raw API payload into ConfigurationView.
 */

// ── View model ──

interface ConfigurationView {
  settings: ConfigSettingView[]
  thresholds: ConfigThresholdView[]
  featureFlags: FeatureFlagView[]
}

interface ConfigSettingView {
  key: string
  value: unknown
  type: 'string' | 'number' | 'boolean' | 'json'
}

interface ConfigThresholdView {
  name: string
  warning: number
  critical: number
}

interface FeatureFlagView {
  key: string
  enabled: boolean
  description?: string
}

// ── Normalizer ──

function normalizeConfiguration(raw: Record<string, unknown>): ConfigurationView {
  return {
    settings: (raw.settings as ConfigSettingView[]) ?? [],
    thresholds: (raw.thresholds as ConfigThresholdView[]) ?? [],
    featureFlags: (raw.featureFlags as FeatureFlagView[]) ?? [],
  }
}

export { normalizeConfiguration }
export type { ConfigurationView, ConfigSettingView, ConfigThresholdView, FeatureFlagView }
