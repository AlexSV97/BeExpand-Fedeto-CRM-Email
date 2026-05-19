/**
 * TimeSeriesCharts — Analizador de series temporales y predicciones.
 *
 * Renderiza:
 * - Selector de período (7d / 30d / 90d / Todo)
 * - Grid 2×2 con 4 gráficos Recharts
 * - Sección de forecasting con predicción a 30 días
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
  cliente: '#0ea5e9',
  lead: '#f59e0b',
  proveedor: '#22c55e',
  nulo: '#94a3b8',
  sin_categoria: '#94a3b8',
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

const PERIODS = [
  { key: '7d', label: '7 días' },
  { key: '30d', label: '30 días' },
  { key: '90d', label: '90 días' },
  { key: 'all', label: 'Todo' },
]

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
  const [period, setPeriod] = useState('30d')
  const [forecastDays, setForecastDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getTimeSeries(period)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [period])

  // Datos derivados
  const stackedData = useMemo(
    () => (data ? toStackedData(data.by_category) : []),
    [data?.by_category],
  )
  const categories = useMemo(
    () => extractCategories(stackedData),
    [stackedData],
  )

  const volumeData = useMemo(
    () =>
      (data?.volume ?? []).map((p) => ({
        date: formatDate(p.date),
        value: p.value,
      })),
    [data?.volume],
  )

  const confidenceData = useMemo(
    () =>
      (data?.avg_confidence ?? []).map((p) => ({
        date: formatDate(p.date),
        confidence: formatConfidence(p.value),
        raw: p.value,
      })),
    [data?.avg_confidence],
  )

  const contactsData = useMemo(
    () =>
      (data?.contacts_cumulative ?? []).map((p) => ({
        date: formatDate(p.date),
        value: p.value,
      })),
    [data?.contacts_cumulative],
  )

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

  const hasData = data && data.volume.length > 0

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />

  return (
    <div className="space-y-6">
      {/* Cabecera + selector de período */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            Series Temporales y Predicciones
          </h3>
          <p className="text-sm text-slate-500 mt-0.5">
            Evolución del sistema y proyecciones a 30, 60 y 90 días
          </p>
        </div>
        <PeriodSelector current={period} onChange={setPeriod} />
      </div>

      {!hasData ? (
        <EmptyState />
      ) : (
        <>
          {/* Grid 2×2 de gráficos */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 1. Volumen de correos */}
            <ChartCard title="Volumen de correos">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={volumeData}>
                  <defs>
                    <linearGradient id="volumeGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    fill="url(#volumeGrad)"
                    name="Correos"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 2. Correos por categoría (stacked) */}
            <ChartCard title="Correos por categoría">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={stackedData}>
                  <defs>
                    {categories.map((cat) => (
                      <linearGradient key={cat} id={`stackGrad-${cat}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={CATEGORY_COLORS[cat] ?? '#94a3b8'} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={CATEGORY_COLORS[cat] ?? '#94a3b8'} stopOpacity={0.02} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  {categories.map((cat) => (
                    <Area
                      key={cat}
                      type="monotone"
                      dataKey={cat}
                      stackId="1"
                      stroke={CATEGORY_COLORS[cat] ?? '#94a3b8'}
                      fill={`url(#stackGrad-${cat})`}
                      name={CATEGORY_LABELS[cat] ?? cat}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 3. Confianza media */}
            <ChartCard title="Precisión media del modelo">
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={confidenceData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip formatter={(value: unknown) => [formatConfidence(Number(value) || 0), 'Confianza']} />
                  <Line
                    type="monotone"
                    dataKey="raw"
                    stroke="#8b5cf6"
                    strokeWidth={2}
                    dot={false}
                    name="Confianza"
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* 4. Contactos acumulados */}
            <ChartCard title="Contactos capturados">
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={contactsData}>
                  <defs>
                    <linearGradient id="contactsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="url(#contactsGrad)"
                    name="Contactos"
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
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-sm font-bold text-slate-900">
            Predicción — Próximos {forecastDays} días
          </h4>
          {summary && (
            <p className="text-sm text-slate-600 mt-0.5">
              Se esperan <strong className="text-slate-900">~{summary.total} correos</strong> en los próximos {forecastDays} días,
              con mayoría de{' '}
              {summary.top.slice(0, 2).map((c, i) => (
                <span key={c.category}>
                  {i > 0 ? ' y ' : ''}
                  <strong className="text-slate-900">{c.category.toLowerCase()} ({Math.round(c.predicted_count)})</strong>
                </span>
              ))}
              .
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Selector de horizonte */}
          <div className="inline-flex items-center gap-0.5 bg-slate-50 rounded-md p-0.5">
            {FORECAST_HORIZONS.map((d) => (
              <button
                key={d}
                onClick={() => onForecastDaysChange(d)}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all duration-150 cursor-pointer
                  ${forecastDays === d
                    ? 'bg-white text-slate-900 shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-700'
                  }`}
              >
                {d}d
              </button>
            ))}
          </div>
          <span className="inline-flex items-center px-2 py-1 rounded-md text-[10px] font-mono font-semibold bg-slate-100 text-slate-500">
            {forecast.method}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bar chart: predicción por categoría */}
        <div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="category" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
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
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Tendencia por categoría
          </p>
          <div className="space-y-2">
            {forecast.by_category.map((c) => {
              const trendInfo = TREND_LABELS[c.trend] ?? TREND_LABELS.stable
              return (
                <div
                  key={c.category}
                  className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-50"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: CATEGORY_COLORS[c.category] ?? '#94a3b8' }}
                    />
                    <span className="text-sm font-medium text-slate-700">
                      {CATEGORY_LABELS[c.category] ?? c.category}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold text-slate-900 tabular-nums">
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

function PeriodSelector({
  current,
  onChange,
}: {
  current: string
  onChange: (p: string) => void
}) {
  return (
    <div className="inline-flex items-center gap-1 bg-slate-100 rounded-lg p-1">
      {PERIODS.map((p) => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all duration-150 cursor-pointer
            ${current === p.key
              ? 'bg-white text-slate-900 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
            }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

function ChartCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
      <h4 className="text-sm font-semibold text-slate-700 mb-3">{title}</h4>
      {children}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="text-center">
        <div className="w-6 h-6 border-3 border-sky-200 border-t-sky-500 rounded-full animate-spin mx-auto" />
        <p className="mt-3 text-sm text-slate-500">Cargando series temporales...</p>
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800">
      Error al cargar series temporales: {message}
    </div>
  )
}

function EmptyState() {
  return (
    <div className="bg-white rounded-xl p-8 shadow-sm border border-slate-100 text-center">
      <svg
        className="w-10 h-10 mx-auto text-slate-300 mb-3"
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
      <p className="text-sm text-slate-500">
        No hay suficientes datos para mostrar series temporales.
      </p>
      <p className="text-xs text-slate-400 mt-1">
        Los gráficos aparecerán cuando el sistema haya procesado correos durante varios días.
      </p>
    </div>
  )
}
