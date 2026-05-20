/**
 * EmailDetail — Página de detalle de un correo electrónico.
 *
 * Muestra el cuerpo completo, metadatos, clasificación multi-agente,
 * historial de revisiones y acciones disponibles.
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getEmail, type EmailDetail, type ClassificationHistoryItem } from '../services/api'

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

const METHOD_LABELS: Record<string, string> = {
  rule_engine: 'Reglas',
  bert: 'BERT',
  llm: 'Ollama',
  orchestrator_consensus: 'Consenso',
  orchestrator_majority: 'Mayoría',
  orchestrator_llm_judge: 'Juez LLM',
  orchestrator_fallback: 'Fallback',
  manual_review: 'Revisión manual',
  unknown: 'Desconocido',
}

const METHOD_COLORS: Record<string, string> = {
  rule_engine: '#3b82f6',
  bert: '#8b5cf6',
  llm: '#22c55e',
  orchestrator_consensus: '#0ea5e9',
  orchestrator_majority: '#f59e0b',
  orchestrator_llm_judge: '#8b5cf6',
  orchestrator_fallback: '#94a3b8',
  manual_review: '#f97316',
}

const RESOLUTION_LABELS: Record<string, string> = {
  consensus: 'Consenso',
  majority: 'Mayoría',
  llm_judge: 'Juez LLM',
  fallback: 'Fallback',
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

// ── Helpers ──

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('es-ES', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatConfidence(conf: number): string {
  return `${Math.round(conf * 100)}%`
}

function extractAnalyzer(extra: Record<string, unknown> | null) {
  if (!extra) return null
  const analyzer = extra.analyzer as Record<string, unknown> | undefined
  if (!analyzer) return null
  return {
    company: analyzer.company as string | null,
    urgency: analyzer.urgency as string | null,
    action_required: analyzer.action_required as string | null,
    entities: analyzer.entities as string[] | null,
  }
}

function extractRouting(extra: Record<string, unknown> | null) {
  if (!extra) return null
  const routing = extra.routing as Record<string, unknown> | undefined
  if (!routing) return null
  return {
    departments: (routing.departments as string[]) ?? [],
    persons: (routing.persons as string[]) ?? [],
    rationale: routing.rationale as string | null,
  }
}

function extractVotes(extra: Record<string, unknown> | null) {
  if (!extra) return null
  return (extra.votes as { agent: string; category: string; confidence: number }[]) ?? null
}

// ── Componente principal ──

export default function EmailDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [email, setEmail] = useState<EmailDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getEmail(id)
      .then(setEmail)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  if (!email) return <ErrorState message="Correo no encontrado" />

  const category = email.category ?? 'pendiente'
  const catColor = CATEGORY_COLORS[category] ?? '#94a3b8'
  const analyzer = extractAnalyzer(email.extra_data)
  const routing = extractRouting(email.extra_data)
  const votes = extractVotes(email.extra_data)
  const resolution = email.extra_data?.resolution_method as string | null

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Cabecera con volver */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium
            text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          Volver al dashboard
        </button>
      </div>

      {/* Header del correo */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
        <div className="flex items-start gap-3 mb-4">
          <span
            className="shrink-0 w-3 h-3 rounded-full mt-1.5"
            style={{ backgroundColor: catColor }}
          />
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-slate-900 leading-snug">
              {email.subject ?? '(sin asunto)'}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {email.sender_name ?? email.sender_email}
              {email.sender_name && <span className="text-slate-400"> &lt;{email.sender_email}&gt;</span>}
            </p>
          </div>
          <span
            className="shrink-0 inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
            style={{
              backgroundColor: `${catColor}18`,
              color: catColor,
            }}
          >
            {CATEGORY_LABELS[category] ?? category}
          </span>
        </div>

        {/* Metadatos en grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg text-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recibido</p>
            <p className="mt-0.5 text-slate-700">{formatDateTime(email.received_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Procesado</p>
            <p className="mt-0.5 text-slate-700">{formatDateTime(email.processed_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Relevancia</p>
            <p className="mt-0.5 text-slate-700 capitalize">{email.relevance ?? 'media'}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Estado</p>
            <p className="mt-0.5 text-slate-700 capitalize">{email.status ?? 'pendiente'}</p>
          </div>
        </div>

        {/* Tags: urgencia, departamentos, resolución */}
        {(analyzer?.urgency || routing?.departments?.length || resolution) && (
          <div className="flex flex-wrap items-center gap-2 mt-4">
            {analyzer?.urgency && analyzer.urgency !== 'media' && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                style={{
                  backgroundColor: `${URGENCY_COLORS[analyzer.urgency]}15`,
                  color: URGENCY_COLORS[analyzer.urgency],
                }}
              >
                {URGENCY_LABELS[analyzer.urgency] ?? analyzer.urgency}
              </span>
            )}
            {routing?.departments?.map((dept) => (
              <span
                key={dept}
                className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-indigo-50 text-indigo-600"
              >
                {DEPARTMENT_LABELS[dept] ?? dept}
              </span>
            ))}
            {resolution && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-600">
                {RESOLUTION_LABELS[resolution] ?? resolution}
              </span>
            )}
          </div>
        )}

        {/* Resumen IA */}
        {email.summary && (
          <div className="mt-4 p-4 bg-sky-50 border border-sky-100 rounded-lg">
            <p className="text-xs font-semibold uppercase tracking-wider text-sky-600 mb-1">
              Resumen IA
            </p>
            <p className="text-sm text-slate-700 leading-relaxed">{email.summary}</p>
          </div>
        )}
      </div>

      {/* Cuerpo del correo */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
        <h2 className="text-sm font-bold text-slate-900 mb-3">Contenido del correo</h2>
        {email.body_plain ? (
          <pre className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap font-sans">
            {email.body_plain}
          </pre>
        ) : (
          <p className="text-sm text-slate-400 italic">No hay contenido disponible</p>
        )}
      </div>

      {/* Clasificación multi-agente */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
        <h2 className="text-sm font-bold text-slate-900 mb-3">Clasificación multi-agente</h2>

        {votes && (
          <div className="space-y-2 mb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Votos de los agentes</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {votes.map((vote) => (
                <div
                  key={vote.agent}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-50"
                >
                  <span className="text-xs font-semibold text-slate-500 uppercase">
                    {METHOD_LABELS[vote.agent] ?? vote.agent}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: CATEGORY_COLORS[vote.category] ?? '#94a3b8' }}
                    />
                    <span className="text-xs font-medium text-slate-700">
                      {CATEGORY_LABELS[vote.category] ?? vote.category}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      {formatConfidence(vote.confidence)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Resolución */}
        {(email.extra_data?.resolution_method as string) && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-100">
            <span className="text-xs font-semibold text-amber-700">Resolución:</span>
            <span className="text-xs font-medium text-amber-800">
              {RESOLUTION_LABELS[resolution!] ?? resolution}
            </span>
          </div>
        )}
      </div>

      {/* Historial de clasificaciones */}
      {email.classification_history.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-100">
          <h2 className="text-sm font-bold text-slate-900 mb-3">Historial de clasificaciones</h2>
          <div className="space-y-2">
            {[...email.classification_history]
              .sort((a, b) => {
                if (!a.created_at || !b.created_at) return 0
                return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
              })
              .map((ch) => (
                <ChRow key={ch.id} entry={ch} />
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Subcomponentes ──

function ChRow({ entry }: { entry: ClassificationHistoryItem }) {
  const methodLabel = METHOD_LABELS[entry.method] ?? entry.method
  const methodColor = METHOD_COLORS[entry.method] ?? '#94a3b8'
  const catColor = CATEGORY_COLORS[entry.category] ?? '#94a3b8'

  return (
    <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-slate-50">
      <div className="flex items-center gap-3">
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: catColor }} />
        <div>
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold"
            style={{
              backgroundColor: `${methodColor}18`,
              color: methodColor,
            }}
          >
            {methodLabel}
          </span>
          {entry.reviewed && (
            <span className="ml-1.5 text-[10px] font-semibold text-amber-600">Revisado</span>
          )}
        </div>
        <span className="text-xs font-medium text-slate-700 capitalize">
          {CATEGORY_LABELS[entry.category] ?? entry.category}
        </span>
        <span className="text-xs font-mono text-slate-400">{formatConfidence(entry.confidence)}</span>
      </div>
      <span className="text-[10px] text-slate-400">
        {entry.created_at ? formatDateTime(entry.created_at) : ''}
      </span>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="w-8 h-8 border-4 border-sky-200 border-t-sky-500 rounded-full animate-spin mx-auto" />
        <p className="mt-4 text-sm text-slate-500">Cargando correo...</p>
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
