/**
 * ConfigurationSurface — SOC-specific configuration.
 *
 * Section cards for notification thresholds, SLA definitions, surface
 * visibility toggles, and integration settings. Uses useSocResource
 * for data fetching with mock fallback and demo mode badge.
 */

import { useState } from 'react'
import { SURFACE_IDS } from '../../services/soc/contracts'
import type { SocError } from '../../services/soc/contracts'
import { SOC_ENDPOINTS } from '../../services/soc/endpoints'
import { useSocResource } from '../../services/soc/useSocResource'
import { normalizeConfiguration } from '../../services/soc/normalize/configuration'
import { MOCK_CONFIGURATION } from '../../services/soc/mockData'
import { surfaceRegistry } from '../../services/soc/surfaceRegistry'
import { SocLoadingState, SocErrorState } from '../../components/soc'
import { t } from '../../content/socCopy'
import { cn } from '../../lib/utils'
import {
  Settings,
  Bell,
  Clock,
  Eye,
  Link,
  Key,
  Save,
  Check,
  AlertTriangle,
} from 'lucide-react'

// ─── Constants ───────────────────────────────────────────────────────────

const SURFACE_ID = SURFACE_IDS.CONFIGURATION

// ─── Types ────────────────────────────────────────────────────────────────

interface SlaTier {
  id: string
  name: string
  targetSeconds: number
  editable: boolean
}

interface SurfaceToggle {
  id: string
  label: string
  enabled: boolean
}

const MOCK_SURFACES: SurfaceToggle[] = surfaceRegistry.getAll().map((s) => ({
  id: s.id,
  label: s.label,
  enabled: s.enabled,
}))

// ─── Sub-components ───────────────────────────────────────────────────────

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: typeof Settings
  children: React.ReactNode
}) {
  return (
    <div className="bg-card rounded-2xl border border-border/50 shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border/30">
        <Icon className="h-4 w-4 text-chart-1" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <div className="p-5 space-y-4">
        {children}
      </div>
    </div>
  )
}

function ConfigRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="shrink-0">
        {children}
      </div>
    </div>
  )
}

function ToggleSwitch({
  enabled,
  onChange,
}: {
  enabled: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className={cn(
        'relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer',
        enabled ? 'bg-primary' : 'bg-muted-foreground/30',
      )}
    >
      <span
        className={cn(
          'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
          enabled ? 'translate-x-[18px]' : 'translate-x-[3px]',
        )}
      />
    </button>
  )
}

function InputField({
  value,
  onChange,
  type = 'text',
  suffix,
}: {
  value: string
  onChange: (v: string) => void
  type?: string
  suffix?: string
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'w-24 px-3 py-1.5 text-sm bg-muted/50 border border-border/50 rounded-lg',
          'text-foreground text-right font-mono focus:outline-none focus:ring-1 focus:ring-ring',
        )}
      />
      {suffix && <span className="text-xs text-muted-foreground">{suffix}</span>}
    </div>
  )
}

function SliderInput({
  value,
  onChange,
  min = 0,
  max = 100,
  unit = '%',
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  unit?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32 accent-primary"
      />
      <span className="text-sm font-mono font-medium text-foreground min-w-[48px] text-right">
        {value}{unit}
      </span>
    </div>
  )
}

// ─── Main surface ─────────────────────────────────────────────────────────

export default function ConfigurationSurface() {
  const { loading, error, source, refresh } = useSocResource(
    SOC_ENDPOINTS[SURFACE_IDS.CONFIGURATION],
    normalizeConfiguration,
    MOCK_CONFIGURATION,
    SURFACE_ID,
  )

  const [saved, setSaved] = useState(false)

  // ── Local form state ──
  const [slaWarningPct, setSlaWarningPct] = useState(80)
  const [breachAlertDelay, setBreachAlertDelay] = useState('5')
  const [escalationTimeout, setEscalationTimeout] = useState('30')

  const [slaTiers, setSlaTiers] = useState<SlaTier[]>([
    { id: 'critical', name: t('ticket.priority.critical'), targetSeconds: 3600, editable: true },
    { id: 'high', name: t('ticket.priority.high'), targetSeconds: 14400, editable: true },
    { id: 'medium', name: t('ticket.priority.medium'), targetSeconds: 28800, editable: true },
    { id: 'low', name: t('ticket.priority.low'), targetSeconds: 86400, editable: true },
  ])

  const [surfaceToggles, setSurfaceToggles] = useState<SurfaceToggle[]>(MOCK_SURFACES)

  const [webhookUrl, setWebhookUrl] = useState('https://hooks.soc.fedeto.com/events')
  const [apiKey, setApiKey] = useState('sk-••••••••••••••••a3f8')
  const [syncInterval, setSyncInterval] = useState('300')

  // ── Handlers ──
  const handleSave = () => {
    console.log('[Configuration] Saving settings:', {
      slaWarningPct, breachAlertDelay, escalationTimeout, slaTiers, surfaceToggles, webhookUrl, syncInterval,
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleSlaTargetChange = (id: string, value: string) => {
    setSlaTiers((prev) =>
      prev.map((tier) =>
        tier.id === id ? { ...tier, targetSeconds: Number(value) * 3600 } : tier,
      ),
    )
  }

  const handleSurfaceToggle = (id: string, enabled: boolean) => {
    setSurfaceToggles((prev) =>
      prev.map((s) => (s.id === id ? { ...s, enabled } : s)),
    )
  }

  const formatSlaHours = (seconds: number): string => {
    return String(Math.round(seconds / 3600))
  }

  const isDemo = source === 'mock'

  // ── Loading ──
  if (loading) {
    return <SocLoadingState surfaceLabel={t('surfaces.configuration')} />
  }

  // ── Error ──
  if (error) {
    const socErr: SocError = { code: 'FETCH_ERROR', message: error, retry: refresh }
    return <SocErrorState error={socErr} />
  }

  // ── Content ──
  return (
    <div className="space-y-4">
      {/* Header + demo badge */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">{t('surfaces.configuration')}</h2>
          {isDemo && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs font-medium">
              <AlertTriangle className="h-3.5 w-3.5" />
              {"Demo"}
            </div>
          )}
        </div>
        <button
          onClick={handleSave}
          className={cn(
            'inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-xl transition-all cursor-pointer',
            saved
              ? 'bg-success/10 text-success border border-success/20'
              : 'bg-primary text-primary-foreground hover:bg-primary/90',
          )}
        >
          {saved ? (
            <><Check className="h-4 w-4" />{t('config.saved')}</>
          ) : (
            <><Save className="h-4 w-4" />{t('config.save')}</>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Notification Thresholds ── */}
        <SectionCard title={t('config.notificationThresholds')} icon={Bell}>
          <ConfigRow label={t('config.slaWarningLabel')} description={t('config.slaWarningDesc')}>
            <SliderInput value={slaWarningPct} onChange={setSlaWarningPct} min={50} max={100} unit="%" />
          </ConfigRow>
          <ConfigRow label={t('config.breachAlertDelay')} description={t('config.breachAlertDelayDesc')}>
            <InputField value={breachAlertDelay} onChange={setBreachAlertDelay} type="number" suffix={t('config.minutes')} />
          </ConfigRow>
          <ConfigRow label={t('config.escalationTimeout')} description={t('config.escalationTimeoutDesc')}>
            <InputField value={escalationTimeout} onChange={setEscalationTimeout} type="number" suffix={t('config.minutes')} />
          </ConfigRow>
        </SectionCard>

        {/* ── SLA Definitions ── */}
        <SectionCard title={t('config.slaDefinitions')} icon={Clock}>
          <div className="space-y-3">
            {slaTiers.map((tier) => (
              <div key={tier.id} className="flex items-center justify-between py-2 border-b border-border/20 last:border-b-0">
                <span className="text-sm font-medium text-foreground">{tier.name}</span>
                {tier.editable ? (
                  <div className="flex items-center gap-2">
                    <input type="number" value={formatSlaHours(tier.targetSeconds)}
                      onChange={(e) => handleSlaTargetChange(tier.id, e.target.value)}
                      className="w-16 px-2 py-1 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground text-center font-mono focus:outline-none focus:ring-1 focus:ring-ring" min={1} />
                    <span className="text-xs text-muted-foreground">{t('config.hours')}</span>
                  </div>
                ) : (
                  <span className="text-sm font-mono text-muted-foreground">{formatSlaHours(tier.targetSeconds)} {t('config.hours')}</span>
                )}
              </div>
            ))}
          </div>
        </SectionCard>

        {/* ── Surface Visibility ── */}
        <SectionCard title={t('config.surfaceVisibility')} icon={Eye}>
          <div className="space-y-2">
            {surfaceToggles.map((surface) => (
              <div key={surface.id} className="flex items-center justify-between py-2 border-b border-border/20 last:border-b-0">
                <span className="text-sm text-foreground">{surface.label}</span>
                <ToggleSwitch enabled={surface.enabled} onChange={(v) => handleSurfaceToggle(surface.id, v)} />
              </div>
            ))}
          </div>
        </SectionCard>

        {/* ── Integration Settings ── */}
        <SectionCard title={t('config.integrationSettings')} icon={Link}>
          <ConfigRow label={t('config.webhookUrl')} description={t('config.webhookUrlDesc')}>
            <input type="text" value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)}
              className="w-full max-w-[240px] px-3 py-1.5 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring" />
          </ConfigRow>
          <ConfigRow label={t('config.apiKey')} description={t('config.apiKeyDesc')}>
            <div className="flex items-center gap-2">
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                className="w-full max-w-[180px] px-3 py-1.5 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring" />
              <Key className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </div>
          </ConfigRow>
          <ConfigRow label={t('config.syncInterval')} description={t('config.syncIntervalDesc')}>
            <div className="flex items-center gap-2">
              <input type="number" value={syncInterval} onChange={(e) => setSyncInterval(e.target.value)}
                className="w-20 px-3 py-1.5 text-sm bg-muted/50 border border-border/50 rounded-lg text-foreground text-right font-mono focus:outline-none focus:ring-1 focus:ring-ring" min={30} />
              <span className="text-xs text-muted-foreground">{t('config.seconds')}</span>
            </div>
          </ConfigRow>
        </SectionCard>
      </div>
    </div>
  )
}

