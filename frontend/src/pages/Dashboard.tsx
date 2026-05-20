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
import { useNavigate } from 'react-router-dom'
import {
  getDashboardSummary,
  syncEmails,
  reviewEmail,
  retrainModel,
  syncCrm,
  type CrmSyncResponse,
  type DashboardSummary,
  type RecentEmailItem,
  type RetrainResponse,
} from '../services/api'
import TimeSeriesCharts from '../components/TimeSeriesCharts'

// ── Constantes ──

const CATEGORY_COLORS: Record<string, string> = {
  cliente: '#0ea5e9',
  lead: '#f59e0b',
  proveedor: '#22c55e',
  nulo: '#94a3b8',
  pendiente: '#94a3b8',
}

const CATEGORY_LABELS: Record<string, string> = {
  cliente: 'Cliente',
  lead: 'Lead',
  proveedor: 'Proveedor',
  nulo: 'Spam / Nulo',
}

const CATEGORY_OPTIONS = ['cliente', 'lead', 'proveedor', 'nulo'] as const

const METHOD_LABELS: Record<string, string> = {
  rule_engine: 'Reglas',
  bert: 'BERT',
  ollama: 'Ollama',
  hybrid_fallback: 'Fallback',
  orchestrator_consensus: 'Consenso',
  orchestrator_majority: 'Mayoría',
  orchestrator_llm_judge: 'Juez LLM',
  orchestrator_fallback: 'Fallback',
  unknown: 'Desconocido',
}

const METHOD_COLORS: Record<string, string> = {
  rule_engine: '#3b82f6',
  bert: '#8b5cf6',
  ollama: '#22c55e',
  hybrid_fallback: '#94a3b8',
  orchestrator_consensus: '#0ea5e9',
  orchestrator_majority: '#f59e0b',
  orchestrator_llm_judge: '#8b5cf6',
  orchestrator_fallback: '#94a3b8',
  unknown: '#cbd5e1',
}

const RESOLUTION_LABELS: Record<string, string> = {
  consensus: 'Consenso',
  majority: 'Mayoría',
  llm_judge: 'Juez LLM',
  fallback: 'Fallback',
}

const RESOLUTION_COLORS: Record<string, string> = {
  consensus: '#0ea5e9',
  majority: '#f59e0b',
  llm_judge: '#8b5cf6',
  fallback: '#94a3b8',
}

const URGENCY_LABELS: Record<string, string> = {
  alta: 'Urgente',
  media: 'Normal',
  baja: 'Baja',
}

const URGENCY_COLORS: Record<string, string> = {
  alta: '#ef4444',
  media: '#f59e0b',
  baja: '#94a3b8',
}

const DEPARTMENT_LABELS: Record<string, string> = {
  contabilidad: 'Contabilidad',
  soporte: 'Soporte',
  comercial: 'Comercial',
  proveedores: 'Proveedores',
  direccion: 'Dirección',
  otro: 'Otro',
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
  const [expandedSummary, setExpandedSummary] = useState<string | null>(null)
  const [syncingCrm, setSyncingCrm] = useState(false)
  const [crmResult, setCrmResult] = useState<CrmSyncResponse | null>(null)
  const [crmError, setCrmError] = useState<string | null>(null)
  const [retraining, setRetraining] = useState(false)
  const [retrainResult, setRetrainResult] = useState<RetrainResponse | null>(null)
  const [retrainError, setRetrainError] = useState<string | null>(null)
  const [reviewingId, setReviewingId] = useState<string | null>(null)
  const [reviewFeedback, setReviewFeedback] = useState<{
    id: string
    success: boolean
    text: string
  } | null>(null)

  const clearReviewFeedback = useCallback(() => {
    setReviewFeedback(null)
  }, [])

  const handleSyncCrm = useCallback(async () => {
    setSyncingCrm(true)
    setCrmResult(null)
    setCrmError(null)
    try {
      const result = await syncCrm()
      setCrmResult(result)
    } catch (e: unknown) {
      setCrmError(e instanceof Error ? e.message : 'Error al sincronizar CRM')
    } finally {
      setSyncingCrm(false)
    }
  }, [])

  const handleRetrain = useCallback(async () => {
    setRetraining(true)
    setRetrainResult(null)
    setRetrainError(null)
    try {
      const result = await retrainModel({ epochs: 6 })
      setRetrainResult(result)
    } catch (e: unknown) {
      setRetrainError(e instanceof Error ? e.message : 'Error al re-entrenar')
    } finally {
      setRetraining(false)
    }
  }, [])

  const handleReview = useCallback(async (emailId: string, category: string) => {
    setReviewingId(emailId)
    setReviewFeedback(null)
    try {
      await reviewEmail(emailId, category)
      setReviewFeedback({ id: emailId, success: true, text: 'Revisado correctamente' })
      getDashboardSummary().then(setData).catch(() => {})
      setTimeout(clearReviewFeedback, 3000)
    } catch (e: unknown) {
      setReviewFeedback({
        id: emailId,
        success: false,
        text: e instanceof Error ? e.message : 'Error al revisar',
      })
      setTimeout(clearReviewFeedback, 5000)
    } finally {
      setReviewingId(null)
    }
  }, [clearReviewFeedback])

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
      const categorized = result.results.filter(r => r.category && r.category !== 'nulo')
      const nulos = result.results.filter(r => r.category === 'nulo')
      const line = `${result.processed} procesado(s) · ${categorized.length} clasificado(s) · ${nulos.length} nulo(s) · ${result.errors} error(es)`
      setSyncResult(line)
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
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncCrm}
            disabled={syncingCrm}
            className={`
              inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
              transition-all duration-200 shadow-sm border
              ${syncingCrm
                ? 'bg-emerald-100 text-emerald-400 cursor-not-allowed border-emerald-200'
                : 'bg-white text-emerald-700 hover:bg-emerald-50 active:scale-95 border-emerald-300 hover:border-emerald-400'
              }
            `}
          >
            <svg className={`w-4 h-4 ${syncingCrm ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
              <circle cx="8.5" cy="7" r="4" />
              <path d="M20 8v6" />
              <path d="M23 11h-6" />
            </svg>
            {syncingCrm ? 'Sincronizando...' : 'CRM'}
          </button>
          <button
            onClick={handleRetrain}
            disabled={retraining}
            className={`
              inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold
              transition-all duration-200 shadow-sm border
              ${retraining
                ? 'bg-purple-100 text-purple-400 cursor-not-allowed border-purple-200'
                : 'bg-white text-purple-700 hover:bg-purple-50 active:scale-95 border-purple-300 hover:border-purple-400'
              }
            `}
          >
            <svg className={`w-4 h-4 ${retraining ? 'animate-spin' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 2v6h-6" />
              <path d="M3 12a9 9 0 0115.36-6.36L21 8" />
              <path d="M3 22v-6h6" />
              <path d="M21 12a9 9 0 01-15.36 6.36L3 16" />
            </svg>
            {retraining ? 'Re-entrenando...' : 'Re-entrenar modelo'}
          </button>
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

      {/* Feedback retrain */}
      {retraining && (
        <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl text-sm text-purple-800 flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-purple-300 border-t-purple-600 rounded-full animate-spin shrink-0" />
          <div>
            <p className="font-semibold">Re-entrenando modelo BERT...</p>
            <p className="text-xs text-purple-600 mt-0.5">
              Este proceso tarda varios minutos en CPU. No cierres la página.
            </p>
          </div>
        </div>
      )}
      {retrainResult && retrainResult.status === 'success' && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800">
          <div className="flex items-center justify-between mb-2">
            <p className="font-semibold">Re-entrenamiento completado</p>
            <span className="text-[10px] text-emerald-500 font-mono">
              {retrainResult.training_time_seconds?.toFixed(1)}s
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums">{retrainResult.accuracy != null ? `${(retrainResult.accuracy * 100).toFixed(1)}%` : '-'}</p>
              <p className="text-[10px] text-emerald-700">Accuracy</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums">{retrainResult.f1_macro != null ? `${(retrainResult.f1_macro * 100).toFixed(1)}%` : '-'}</p>
              <p className="text-[10px] text-emerald-700">F1 Macro</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums">{retrainResult.real_samples ?? '-'}</p>
              <p className="text-[10px] text-emerald-700">Muestras reales</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums">{retrainResult.train_samples ?? '-'} / {retrainResult.test_samples ?? '-'}</p>
              <p className="text-[10px] text-emerald-700">Train/Test</p>
            </div>
          </div>
        </div>
      )}
      {retrainError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
          Error al re-entrenar: {retrainError}
        </div>
      )}

      {/* Feedback CRM sync */}
      {syncingCrm && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-emerald-300 border-t-emerald-600 rounded-full animate-spin shrink-0" />
          <div>
            <p className="font-semibold">Sincronizando con VTiger CRM...</p>
            <p className="text-xs text-emerald-600 mt-0.5">
              Creando y actualizando contactos en el CRM.
            </p>
          </div>
        </div>
      )}
      {crmResult && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800">
          <div className="flex items-center justify-between mb-2">
            <p className="font-semibold">CRM sincronizado</p>
            <span className="text-[10px] text-emerald-500">{crmResult.total} contacto(s)</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums text-emerald-700">{crmResult.created}</p>
              <p className="text-[10px] text-emerald-700">Creados</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums text-emerald-700">{crmResult.updated}</p>
              <p className="text-[10px] text-emerald-700">Actualizados</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums text-emerald-700">{crmResult.skipped}</p>
              <p className="text-[10px] text-emerald-700">Omitidos</p>
            </div>
            <div className="bg-emerald-100/50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold tabular-nums text-emerald-700">{crmResult.errors}</p>
              <p className="text-[10px] text-emerald-700">Errores</p>
            </div>
          </div>
          {crmResult.errors > 0 && crmResult.results.filter(r => r.action === 'error').length > 0 && (
            <details className="mt-2 text-xs text-red-600">
              <summary className="cursor-pointer font-medium">Ver errores</summary>
              <ul className="mt-1 space-y-1">
                {crmResult.results.filter(r => r.action === 'error').map((r, i) => (
                  <li key={i}>{r.email}: {r.detail}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
      {crmError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
          Error CRM: {crmError}
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
              <EmailRow
                key={email.id}
                email={email}
                isSummaryExpanded={expandedSummary === email.id}
                onToggleSummary={() =>
                  setExpandedSummary(expandedSummary === email.id ? null : email.id)
                }
                onReview={handleReview}
                isReviewing={reviewingId === email.id}
                reviewFeedback={reviewFeedback?.id === email.id ? reviewFeedback : null}
              />
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

      {/* Series temporales y predicciones */}
      <TimeSeriesCharts />
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

function EmailRow({
  email,
  isSummaryExpanded,
  onToggleSummary,
  onReview,
  isReviewing,
  reviewFeedback,
}: {
  email: RecentEmailItem
  isSummaryExpanded: boolean
  onToggleSummary: () => void
  onReview: (emailId: string, category: string) => void
  isReviewing: boolean
  reviewFeedback: { id: string; success: boolean; text: string } | null
}) {
  const [showPicker, setShowPicker] = useState(false)
  const category = email.category ?? 'pendiente'
  const catColor = CATEGORY_COLORS[category] ?? '#94a3b8'
  const methodLabel = METHOD_LABELS[email.method] ?? email.method
  const methodColor = METHOD_COLORS[email.method] ?? '#cbd5e1'
  const hasSummary = !!email.summary && email.summary !== ''
  const hasRouting = email.departments && email.departments.length > 0
  const resolutionLabel = RESOLUTION_LABELS[email.resolution ?? ''] ?? null
  const resolutionColor = RESOLUTION_COLORS[email.resolution ?? ''] ?? null
  const urgencyColor = URGENCY_COLORS[email.urgency] ?? null

  const navigate = useNavigate()
  const handleSelectCategory = (newCategory: string) => {
    setShowPicker(false)
    if (newCategory === category) return
    onReview(email.id, newCategory)
  }

  return (
    <div>
      {/* Fila principal */}
      <div className="flex items-center gap-3 py-3 first:pt-0">
        {/* Badge categoría */}
        <span
          className="shrink-0 w-2 h-2 rounded-full"
          style={{ backgroundColor: catColor }}
          title={category}
        />

        {/* Contenido */}
        <div className="flex-1 min-w-0">
          <button
            onClick={() => navigate(`/emails/${email.id}`)}
            className="text-sm font-medium text-slate-900 truncate text-left hover:text-sky-600 transition-colors cursor-pointer"
            title="Ver detalle del correo"
          >
            {email.subject ?? '(sin asunto)'}
          </button>
          <p className="text-xs text-slate-500 truncate">
            {email.sender_name ?? email.sender_email}
            {email.action_required && (
              <span className="ml-2 text-slate-400">
                · {email.action_required}
              </span>
            )}
          </p>
          {/* Departamentos destino */}
          {hasRouting && (
            <div className="flex flex-wrap gap-1 mt-1">
              {email.departments!.map((dept) => (
                <span
                  key={dept}
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-600"
                >
                  {DEPARTMENT_LABELS[dept] ?? dept}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Feedback inline */}
        {reviewFeedback && (
          <span
            className={`shrink-0 text-xs font-semibold ${reviewFeedback.success ? 'text-emerald-600' : 'text-red-600'}`}
          >
            {reviewFeedback.text}
          </span>
        )}

        {/* Urgencia */}
        {urgencyColor && email.urgency !== 'media' && !reviewFeedback && (
          <span
            className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
            style={{
              backgroundColor: `${urgencyColor}15`,
              color: urgencyColor,
            }}
          >
            {URGENCY_LABELS[email.urgency] ?? email.urgency}
          </span>
        )}

        {/* Botón resumen */}
        {hasSummary && !reviewFeedback && (
          <button
            onClick={onToggleSummary}
            className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
              text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Ver resumen"
          >
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${isSummaryExpanded ? 'rotate-180' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
            Resumen
          </button>
        )}

        {/* Botón Revisar + inline picker */}
        {!isReviewing && !reviewFeedback && (
          <div className="relative">
            <button
              onClick={() => setShowPicker(!showPicker)}
              className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
                text-amber-600 hover:text-amber-800 hover:bg-amber-50 transition-colors border border-transparent hover:border-amber-200"
              title="Revisar clasificación"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 20h9" />
                <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
              Revisar
            </button>
            {showPicker && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowPicker(false)} />
                <div className="absolute right-0 top-full mt-1 z-20 bg-white rounded-lg shadow-lg border border-slate-200 py-1 min-w-[160px]">
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    Cambiar a...
                  </p>
                  {CATEGORY_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => handleSelectCategory(opt)}
                      className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-slate-50 transition-colors
                        ${opt === category ? 'text-slate-400' : 'text-slate-700'}`}
                    >
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: CATEGORY_COLORS[opt] ?? '#94a3b8' }}
                      />
                      {CATEGORY_LABELS[opt] ?? opt}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {isReviewing && (
          <div className="shrink-0 flex items-center gap-1.5 text-xs text-slate-400">
            <div className="w-3 h-3 border-2 border-slate-300 border-t-slate-500 rounded-full animate-spin" />
            Revisando...
          </div>
        )}

        {/* Badge resolución */}
        {resolutionLabel && !reviewFeedback && (
          <span
            className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium"
            style={{
              backgroundColor: `${resolutionColor!}15`,
              color: resolutionColor!,
            }}
          >
            {resolutionLabel}
          </span>
        )}

        {/* Confianza */}
        {!reviewFeedback && (
          <span className="text-xs text-slate-400 font-mono shrink-0 w-10 text-right">
            {formatConfidence(email.confidence)}
          </span>
        )}

        {/* Badge método */}
        {!reviewFeedback && (
          <span
            className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
            style={{
              backgroundColor: `${methodColor}18`,
              color: methodColor,
            }}
          >
            {methodLabel}
          </span>
        )}

        {/* Badge Revisado */}
        {email.reviewed && !reviewFeedback && (
          <span
            className="shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold
              text-amber-700 bg-amber-50 border border-amber-200"
          >
            <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
            </svg>
            Revisado
          </span>
        )}

        {/* Tiempo */}
        {!reviewFeedback && (
          <span className="text-xs text-slate-400 shrink-0 w-16 text-right">
            {formatTimeAgo(email.received_at)}
          </span>
        )}
      </div>

      {/* Panel de resumen expandible + detalles del análisis */}
      {isSummaryExpanded && (
        <div className="ml-6 mb-3 p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm text-slate-700 animate-fadeIn space-y-2">
          {hasSummary && (
            <div className="flex items-start gap-2">
              <svg
                className="w-4 h-4 mt-0.5 shrink-0 text-slate-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M16 13H8" />
                <path d="M16 17H8" />
                <path d="M10 9H8" />
              </svg>
              <p className="leading-relaxed">{email.summary}</p>
            </div>
          )}
          {/* Detalles del análisis */}
          {hasRouting && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 border-t border-slate-200 pt-2 mt-1">
              <span>📬 Enrutado a: <strong>
                {email.departments!.map((d) => DEPARTMENT_LABELS[d] ?? d).join(', ')}
              </strong></span>
              {email.resolution && (
                <span>⚖️ Resolución: <strong>{RESOLUTION_LABELS[email.resolution] ?? email.resolution}</strong></span>
              )}
              {email.action_required && (
                <span>🎯 Acción: <strong>{email.action_required}</strong></span>
              )}
            </div>
          )}
        </div>
      )}
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
