/**
 * TimeSeriesCharts — Forecast puro: predicciones a 30/60/90 días.
 *
 * Renderiza:
 * - Grid 2×2 con 4 gráficos de proyección (sin datos históricos)
 * - Sección de forecasting con desglose por categoría + tendencias
 * - Selector de horizonte (30d / 60d / 90d)
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  getTimeSeries,
  type TimeSeriesResponse,
} from '../services/api'

// ── Constantes ──

const CATEGORY_COLORS: Record<string, string> = {
  cliente: '#14b8a6',
  lead: '#f59e0b',
  proveedor: '#6366f1',
  nulo: '#475569',
  sin_categoria: '#475569',
}

const CATEGORY_LABELS: Record<string, string> = {
  cliente: 'Cliente',
  lead: 'Lead',
  proveedor: 'Proveedor',
  nulo: 'Spam / Nulo',
  sin_categoria: 'Sin categoría',
}

const TREND_LABELS: Record<string, { label: string; color: string }> = {
  increasing: { label: '📈 Al alza', color: '#22c55e' },
  decreasing: { label: '📉 A la baja', color: '#ef4444' },
  stable: { label: '➡️ Estable', color: '#94a3b8' },
}

const FORECAST_HORIZONS = [30, 60, 90]

// ── Helpers ──

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })
}

function formatConfidence(val: number): string {
  return `${(val * 100).toFixed(0)}%`
}

/** Transforma by_category (formato largo) → formato apilado por fecha. */
function toStackedData(
  rows: { date: string; category: string; value: number }[],
): Record<string, unknown>[] {
  const map = new Map<string, Record<string, unknown>>()
  for (const r of rows) {
    if (!map.has(r.date)) {
      map.set(r.date, { date: formatDate(r.date) })
    }
    const entry = map.get(r.date)!
    entry[r.category] = (entry[r.category] as number ?? 0) + r.value
  }
  return Array.from(map.values()).sort(
    (a, b) => new Date(a.date as string).getTime() - new Date(b.date as string).getTime(),
  )
}

/** Extrae las categorías presentes de los datos apilados. */
function extractCategories(data: Record<string, unknown>[]): string[] {
  const cats = new Set<string>()
  for (const entry of data) {
    for (const key of Object.keys(entry)) {
      if (key !== 'date') cats.add(key)
    }
  }
  return Array.from(cats).sort()
}

// ── Componente principal ──

export default function TimeSeriesCharts() {
  const [data, setData] = useState<TimeSeriesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [forecastDays, setForecastDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    setError(null)
    // Usamos '90d' para que el backend entrene con los últimos 90 días
    getTimeSeries('90d')
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // ── Datos exclusivamente de forecast ──

  const volumeForecastData = useMemo(
    () =>
      (data?.volume_forecast ?? [])
        .slice(0, forecastDays)
        .map((p) => ({
          date: formatDate(p.date),
          valor: Math.round(p.value),
        })),
    [data?.volume_forecast, forecastDays],
  )

  const categoryForecastStacked = useMemo(
    () => {
      const sliced = (data?.by_category_forecast ?? []).slice(0, forecastDays * 4)
      return toStackedData(sliced)
    },
    [data?.by_category_forecast, forecastDays],
  )

  const forecastCategories = useMemo(
    () => extractCategories(categoryForecastStacked),
    [categoryForecastStacked],
  )

  const confidenceForecastData = useMemo(
    () =>
      (data?.avg_confidence_forecast ?? [])
        .slice(0, forecastDays)
        .map((p) => ({
          date: formatDate(p.date),
          valor: p.value,
        })),
    [data?.avg_confidence_forecast, forecastDays],
  )

  const contactsForecastData = useMemo(
    () =>
      (data?.contacts_forecast ?? [])
        .slice(0, forecastDays)
        .map((p) => ({
          date: formatDate(p.date),
          valor: Math.round(p.value),
        })),
    [data?.contacts_forecast, forecastDays],
  )

  // Forecast agregado (sección inferior)
  const currentForecast = useMemo(
    () => data?.forecasts.find((f) => f.days === forecastDays) ?? null,
    [data?.forecasts, forecastDays],
  )

  const forecastSummary = useMemo(() => {
    if (!currentForecast) return null
    const f = currentForecast
    const total = Math.round(f.total)
    const top = [...f.by_category].sort((a, b) => b.predicted_count - a.predicted_count)
    return { total, top, days: f.days }
  }, [currentForecast])

  const hasForecast = data && (data.volume_forecast?.length ?? 0) > 0

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold font-display" style={{ color: 'var(--color-text-primary)' }}>
            Predicción de Correos
          </h3>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
            Proyecciones a {forecastDays} días basadas en el histórico del sistema
          </p>
        </div>
        <ForecastHorizonSelector
          horizons={FORECAST_HORIZONS}
          selected={forecastDays}
          onChange={setForecastDays}
        />
      </div>

      {!hasForecast ? (
        <EmptyState />
      ) : (
        <>
          {/* Grid 2×2 de gráficos — solo forecast */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 1. Volumen de correos pronosticado */}
            <ChartCard title="Volumen de correos pronosticado">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={volumeForecastData}>
                  <defs>
                    <linearGradient id="volFcGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <Tooltip
                    labelFormatter={(label) => `Fecha: ${label}`}
                    formatter={(value: unknown) => [`${Math.round(Number(value) || 0)} correos`, 'Pronóstico']}
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="valor"
                    stroke="#14b8a6"
                    strokeWidth={2}
                    fill="url(#volFcGrad)"
                    name="Pronóstico"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 2. Correos por categoría pronosticado */}
            <ChartCard title="Correos por categoría pronosticado">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={categoryForecastStacked}>
                  <defs>
                    {forecastCategories.map((cat) => (
                      <linearGradient key={cat} id={`stackFcGrad-${cat}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CATEGORY_COLORS[cat] ?? '#94a3b8'} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={CATEGORY_COLORS[cat] ?? '#94a3b8'} stopOpacity={0.02} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ color: '#94a3b8', fontSize: '11px' }} />
                  {forecastCategories.map((cat) => (
                    <Area
                      key={cat}
                      type="monotone"
                      dataKey={cat}
                      stackId="1"
                      stroke={CATEGORY_COLORS[cat] ?? '#94a3b8'}
                      fill={`url(#stackFcGrad-${cat})`}
                      name={CATEGORY_LABELS[cat] ?? cat}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 3. Precisión media pronosticada */}
            <ChartCard title="Precisión media del modelo">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={confidenceForecastData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} interval="preserveStartEnd" />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: '#64748b' }}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    labelFormatter={(label) => `Fecha: ${label}`}
                    formatter={(value: unknown) => [formatConfidence(Number(value) || 0), 'Precisión']}
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="valor"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={false}
                    name="Pronóstico"
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 4. Contactos capturados pronosticados */}
            <ChartCard title="Contactos capturados">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={contactsForecastData}>
                  <defs>
                    <linearGradient id="ctcFcGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <Tooltip
                    labelFormatter={(label) => `Fecha: ${label}`}
                    formatter={(value: unknown) => [`${Math.round(Number(value) || 0)} contactos`, 'Pronóstico']}
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="valor"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#ctcFcGrad)"
                    name="Pronóstico"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {/* ── Sección de Forecasting ── */}
          {currentForecast && (
            <ForecastSection
              forecast={currentForecast}
              summary={forecastSummary}
              forecastDays={forecastDays}
              onForecastDaysChange={setForecastDays}
            />
          )}
        </>
      )}
    </div>
  )
}

// ── Selector de horizonte ──

function ForecastHorizonSelector({
  horizons,
  selected,
  onChange,
}: {
  horizons: number[]
  selected: number
  onChange: (d: number) => void
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg p-1"
      style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
    >
      {horizons.map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all duration-150 cursor-pointer"
          style={{
            backgroundColor: selected === d ? 'var(--color-bg-card)' : 'transparent',
            color: selected === d ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
            boxShadow: selected === d ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
          }}
          onMouseEnter={e => { if (selected !== d) e.currentTarget.style.color = 'var(--color-text-secondary)'; }}
          onMouseLeave={e => { if (selected !== d) e.currentTarget.style.color = 'var(--color-text-tertiary)'; }}
        >
          {d} días
        </button>
      ))}
    </div>
  )
}

// ── Forecast Section ──

function ForecastSection({
  forecast,
  summary,
  forecastDays,
  onForecastDaysChange,
}: {
  forecast: NonNullable<TimeSeriesResponse['forecasts'][number]>
  summary: { total: number; top: { category: string; predicted_count: number; trend: string }[] } | null
  forecastDays: number
  onForecastDaysChange: (d: number) => void
}) {
  const barData = useMemo(
    () =>
      forecast.by_category.map((c) => ({
        category: CATEGORY_LABELS[c.category] ?? c.category,
        predicted: Math.round(c.predicted_count),
        trend: c.trend,
        fill: CATEGORY_COLORS[c.category] ?? '#94a3b8',
      })),
    [forecast.by_category],
  )

  return (
    <div className="card-solid p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-sm font-bold font-display" style={{ color: 'var(--color-text-primary)' }}>
            Predicción — Próximos {forecastDays} días
          </h4>
          {summary && (
            <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
              Se esperan <strong style={{ color: 'var(--color-text-primary)' }}>~{summary.total} correos</strong> en los próximos {forecastDays} días,
              con mayoría de{' '}
              {summary.top.slice(0, 2).map((c, i) => (
                <span key={c.category}>
                  {i > 0 ? ' y ' : ''}
                  <strong style={{ color: 'var(--color-text-primary)' }}>{c.category.toLowerCase()} ({Math.round(c.predicted_count)})</strong>
                </span>
              ))}
              .
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Selector de horizonte */}
          <div className="inline-flex items-center gap-0.5 rounded-md p-0.5"
            style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
          >
            {FORECAST_HORIZONS.map((d) => (
              <button
                key={d}
                onClick={() => onForecastDaysChange(d)}
                className="px-2.5 py-1 rounded text-[11px] font-semibold transition-all duration-150 cursor-pointer"
                style={{
                  backgroundColor: forecastDays === d ? 'var(--color-bg-card)' : 'transparent',
                  color: forecastDays === d ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                  boxShadow: forecastDays === d ? '0 1px 3px rgba(0,0,0,0.3)' : 'none',
                }}
              >
                {d}d
              </button>
            ))}
          </div>
          <span className="inline-flex items-center px-2 py-1 rounded-md text-[10px] font-mono font-semibold"
            style={{ backgroundColor: 'rgba(255,255,255,0.04)', color: 'var(--color-text-tertiary)' }}
          >
            {forecast.method}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bar chart: predicción por categoría */}
        <div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
<XAxis dataKey="category" tick={{ fontSize: 12, fill: '#94a3b8' }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="predicted" radius={[6, 6, 0, 0]} name="Correos estimados">
                {barData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Tabla de tendencias */}
        <div className="flex flex-col justify-center">
          <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--color-text-tertiary)' }}>
            Tendencia por categoría
          </p>
          <div className="space-y-2">
            {forecast.by_category.map((c) => {
              const trendInfo = TREND_LABELS[c.trend] ?? TREND_LABELS.stable
              return (
                <div
                  key={c.category}
                  className="flex items-center justify-between px-3 py-2 rounded-lg"
                  style={{ backgroundColor: 'var(--color-bg-subtle)' }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: CATEGORY_COLORS[c.category] ?? '#94a3b8' }}
                    />
                    <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      {CATEGORY_LABELS[c.category] ?? c.category}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold tabular-nums" style={{ color: 'var(--color-text-primary)' }}>
                      ~{Math.round(c.predicted_count)}
                    </span>
                    <span
                      className="text-xs font-medium"
                      style={{ color: trendInfo.color }}
                    >
                      {trendInfo.label}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Subcomponentes ──

function ChartCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="card-solid p-5">
      <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>{title}</h4>
      {children}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-center">
        <div className="w-6 h-6 border-3 rounded-full animate-spin mx-auto"
          style={{ borderColor: 'rgba(255,255,255,0.08)', borderTopColor: 'var(--color-accent)' }}
        />
        <p className="mt-3 text-sm" style={{ color: 'var(--color-text-secondary)' }}>Cargando predicciones...</p>
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="p-4 rounded-xl text-sm" style={{ backgroundColor: '#450a0a', border: '1px solid #991b1b', color: '#fca5a5' }}>
      Error al cargar predicciones: {message}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="card-solid p-8 text-center">
      <svg
        className="w-10 h-10 mx-auto mb-3"
        style={{ color: 'var(--color-text-tertiary)' }}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 3v18h18" />
        <path d="M7 16l4-8 4 4 4-6" />
      </svg>
      <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        No hay suficientes datos para generar predicciones.
      </p>
      <p className="text-xs mt-1" style={{ color: 'var(--color-text-tertiary)' }}>
        Las predicciones aparecerán cuando el sistema tenga al menos 2 días de datos históricos.
      </p>
    </div>
  )
}
