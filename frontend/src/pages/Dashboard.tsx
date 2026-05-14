/**
 * Dashboard principal — KPIs, feed de correos y gráficos del sistema.
 *
 * Muestra:
 * - 4 tarjetas KPI con iconos SVG (total correos, hoy, categorías, etapas)
 * - Feed de últimos correos clasificados con badges por método (Reglas/BERT/Ollama)
 * - Donut de distribución por método de clasificación
 * - Barras de contactos por categoría
 * - Pastel de oportunidades por etapa
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import {
  getDashboardSummary,
  syncEmails,
  type DashboardSummary,
  type RecentEmailItem,
} from '../services/api'

// ── Constantes ──

const CATEGORY_COLORS: Record<string, string> = {
  cliente: '#0ea5e9',
  lead: '#f59e0b',
  proveedor: '#22c55e',
  pendiente: '#94a3b8',
}

const METHOD_LABELS: Record<string, string> = {
  rule_engine: 'Reglas',
  bert: 'BERT',
  ollama: 'Ollama',
  hybrid_fallback: 'Fallback',
  unknown: 'Desconocido',
}

const METHOD_COLORS: Record<string, string> = {
  rule_engine: '#3b82f6',
  bert: '#8b5cf6',
  ollama: '#22c55e',
  hybrid_fallback: '#94a3b8',
  unknown: '#cbd5e1',
}

const CHART_COLORS = ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'Ahora'
  if (diffMins < 60) return `Hace ${diffMins} min`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `Hace ${diffHours}h`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return 'Ayer'
  return `Hace ${diffDays} días`
}

function formatConfidence(conf: number): string {
  return `${Math.round(conf * 100)}%`
}

// ── Iconos SVG inline ──

function IconMail() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M22 4L12 13 2 4" />
    </svg>
  )
}

function IconClock() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  )
}

function IconTags() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5H5v4l10 10 4-4L9 5z" />
      <circle cx="7" cy="7" r="1" fill="currentColor" />
    </svg>
  )
}

function IconFunnel() {
  return (
    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16v2L13 14v6l-2 1v-7L4 6V4z" />
    </svg>
  )
}

function IconSync() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2v6h-6" />
      <path d="M3 12a9 9 0 0115.36-6.36L21 8" />
      <path d="M3 22v-6h6" />
      <path d="M21 12a9 9 0 01-15.36 6.36L3 16" />
    </svg>
  )
}

// ── Componente principal ──

export default function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<string | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const fetchDashboard = useCallback(() => {
    getDashboardSummary()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchDashboard()
  }, [fetchDashboard])

  const handleSync = async () => {
    setSyncing(true)
    setSyncResult(null)
    setSyncError(null)
    try {
      const result = await syncEmails()
      const msg = `${result.saved} nuevo(s) · ${result.duplicates} duplicado(s) · ${result.errors} error(es)`
      setSyncResult(msg)
      getDashboardSummary().then(setData).catch(() => {})
    } catch (e: unknown) {
      setSyncError(e instanceof Error ? e.message : 'Error al sincronizar')
    } finally {
      setSyncing(false)
    }
  }

  // Datos derivados
  const contactsData = useMemo(
    () => Object.entries(data?.contacts_by_category ?? {}).map(([name, value]) => ({ name, value })),
    [data?.contacts_by_category],
  )
  const oppsData = useMemo(
    () => Object.entries(data?.opportunities_by_stage ?? {}).map(([name, value]) => ({ name, value })),
    [data?.opportunities_by_stage],
  )
  const methodsData = useMemo(
    () =>
      Object.entries(data?.classification_by_method ?? {})
        .map(([name, value]) => ({
          name: METHOD_LABELS[name] ?? name,
          value,
        }))
        .sort((a, b) => b.value - a.value),
    [data?.classification_by_method],
  )
  const recentEmails = data?.recent_emails ?? []

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  if (!data) return <EmptyState />

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Dashboard</h2>
          <p className="text-sm text-slate-500 mt-1">
            Resumen del sistema de clasificación de correos
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className={`
            inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
            transition-all duration-200 shadow-sm border
            ${syncing
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed border-slate-200'
              : 'bg-white text-slate-700 hover:bg-slate-50 active:scale-95 border-slate-300 hover:border-slate-400'
            }
          `}
        >
          <IconSync />
          {syncing ? 'Sincronizando...' : 'Sincronizar correos'}
        </button>
      </div>

      {/* Feedback sync */}
      {syncResult && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          Sincronización completada: {syncResult}
        </div>
      )}
      {syncError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
          Error: {syncError}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          icon={<IconMail />}
          label="Total correos"
          value={data.total_emails}
          color="text-sky-600"
          bgColor="bg-sky-50"
        />
        <KpiCard
          icon={<IconClock />}
          label="Correos hoy"
          value={data.emails_today}
          color="text-emerald-600"
          bgColor="bg-emerald-50"
        />
        <KpiCard
          icon={<IconTags />}
          label="Categorías activas"
          value={contactsData.length}
          color="text-amber-600"
          bgColor="bg-amber-50"
        />
        <KpiCard
          icon={<IconFunnel />}
          label="Etapas activas"
          value={oppsData.length}
          color="text-purple-600"
          bgColor="bg-purple-50"
        />
      </div>

      {/* Feed de correos recientes */}
      <Card title="Últimos correos clasificados">
        {recentEmails.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {recentEmails.map((email) => (
              <EmailRow key={email.id} email={email} />
            ))}
          </div>
        ) : (
          <EmptyState text="No hay correos clasificados aún" />
        )}
      </Card>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Donut: distribución por método */}
        <Card title="Método de clasificación">
          {methodsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={methodsData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
              label={({ name, percent }: { name?: string; percent?: number }) =>
                `${name ?? ''} ${percent != null ? (percent * 100).toFixed(0) : 0}%`
              }
                >
                  {methodsData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={METHOD_COLORS[entry.name.toLowerCase()] ?? '#94a3b8'}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="Sin datos" />
          )}
        </Card>

        {/* Barras: contactos por categoría */}
        <Card title="Contactos por categoría">
          {contactsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={contactsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {contactsData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={CATEGORY_COLORS[entry.name] ?? '#94a3b8'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="Sin datos" />
          )}
        </Card>

        {/* Pastel: oportunidades por etapa */}
        <Card title="Oportunidades por etapa">
          {oppsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={oppsData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  {oppsData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState text="Sin datos" />
          )}
        </Card>
      </div>
    </div>
  )
}

// ── Subcomponentes ──

function KpiCard({
  icon,
  label,
  value,
  color,
  bgColor,
}: {
  icon: React.ReactNode
  label: string
  value: number
  color: string
  bgColor: string
}) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100 flex items-start gap-4">
      <div className={`${bgColor} ${color} rounded-lg p-3 shrink-0`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </p>
        <p className="mt-1 text-3xl font-bold text-slate-900 tabular-nums">
          {value}
        </p>
      </div>
    </div>
  )
}

function EmailRow({ email }: { email: RecentEmailItem }) {
  const category = email.category ?? 'pendiente'
  const catColor = CATEGORY_COLORS[category] ?? '#94a3b8'
  const methodLabel = METHOD_LABELS[email.method] ?? email.method
  const methodColor = METHOD_COLORS[email.method] ?? '#cbd5e1'

  return (
    <div className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
      {/* Badge categoría */}
      <span
        className="shrink-0 w-2 h-2 rounded-full"
        style={{ backgroundColor: catColor }}
        title={category}
      />

      {/* Contenido */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-900 truncate">
          {email.subject ?? '(sin asunto)'}
        </p>
        <p className="text-xs text-slate-500 truncate">
          {email.sender_name ?? email.sender_email}
        </p>
      </div>

      {/* Confianza */}
      <span className="text-xs text-slate-400 font-mono shrink-0 w-10 text-right">
        {formatConfidence(email.confidence)}
      </span>

      {/* Badge método */}
      <span
        className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
        style={{
          backgroundColor: `${methodColor}18`,
          color: methodColor,
        }}
      >
        {methodLabel}
      </span>

      {/* Tiempo */}
      <span className="text-xs text-slate-400 shrink-0 w-16 text-right">
        {formatTimeAgo(email.received_at)}
      </span>
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
      <h3 className="m-0 mb-4 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="w-8 h-8 border-4 border-sky-200 border-t-sky-500 rounded-full animate-spin mx-auto" />
        <p className="mt-4 text-sm text-slate-500">Cargando dashboard...</p>
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <p className="text-red-500 font-semibold">Error al cargar</p>
        <p className="text-sm text-slate-500 mt-1">{message}</p>
      </div>
    </div>
  )
}

function EmptyState({ text = 'Sin datos disponibles' }: { text?: string }) {
  return (
    <p className="text-slate-400 text-center py-8 text-sm">{text}</p>
  )
}
