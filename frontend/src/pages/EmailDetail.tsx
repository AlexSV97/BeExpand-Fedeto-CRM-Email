/**
 * EmailDetail — Página de detalle de un correo electrónico.
 *
 * Muestra el cuerpo completo, metadatos, clasificación multi-agente,
 * historial de revisiones y acciones disponibles.
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  getEmail,
  reprocessEmail,
  type EmailDetail,
  type ClassificationHistoryItem,
  type ReprocessResponse,
} from '../services/api'

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

function extractSuggestedReply(extra: Record<string, unknown> | null): string | null {
  if (!extra) return null
  return (extra.suggested_reply as string) || null
}

// ── Componente principal ──

export default function EmailDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [email, setEmail] = useState<EmailDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reprocessing, setReprocessing] = useState(false)
  const [reprocessError, setReprocessError] = useState<string | null>(null)
  const [reprocessResult, setReprocessResult] = useState<ReprocessResponse | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getEmail(id)
      .then(setEmail)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleReprocess() {
    if (!id) return
    setReprocessing(true)
    setReprocessError(null)
    setReprocessResult(null)
    try {
      const result = await reprocessEmail(id)
      setReprocessResult(result)
      // Recargar datos frescos del email
      const fresh = await getEmail(id)
      setEmail(fresh)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Error al reprocesar'
      setReprocessError(msg)
    } finally {
      setReprocessing(false)
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} />
  if (!email) return <ErrorState message="Correo no encontrado" />

  const category = email.category ?? 'pendiente'
  const catColor = CATEGORY_COLORS[category] ?? '#94a3b8'
  const analyzer = extractAnalyzer(email.extra_data)
  const routing = extractRouting(email.extra_data)
  const votes = extractVotes(email.extra_data)
  const resolution = email.extra_data?.resolution_method as string | null
  const suggestedReply = extractSuggestedReply(email.extra_data)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Cabecera con volver */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/dashboard')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium
            text-muted-foreground hover:text-foreground hover:bg-secondary/30 transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          Volver al dashboard
        </button>
      </div>

      {/* Header del correo */}
      <div className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm">
        <div className="flex items-start gap-3 mb-4">
          <span
            className="shrink-0 w-3 h-3 rounded-full mt-1.5"
            style={{ backgroundColor: catColor }}
          />
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-foreground leading-snug">
              {email.subject ?? '(sin asunto)'}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {email.sender_name ?? email.sender_email}
              {email.sender_name && <span className="text-muted-foreground"> &lt;{email.sender_email}&gt;</span>}
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <span
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{
                backgroundColor: `${catColor}18`,
                color: catColor,
              }}
            >
              {CATEGORY_LABELS[category] ?? category}
            </span>
            <button
              onClick={handleReprocess}
              disabled={reprocessing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                border border-border/50 hover:bg-secondary/30
                transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed
                text-muted-foreground hover:text-foreground"
              title="Re-clasificar con el pipeline actual"
            >
              {reprocessing ? (
                <>
                  <span className="w-3 h-3 border-2 border-sky-300 border-t-sky-600 rounded-full animate-spin" />
                  Reprocesando...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="23 4 23 10 17 10" />
                    <polyline points="1 20 1 14 7 14" />
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                  </svg>
                  Reprocesar
                </>
              )}
            </button>
          </div>
        </div>

        {/* Resultado del reprocesado */}
        {reprocessResult && (
          <ReprocessSuccessBanner
            result={reprocessResult}
            onDismiss={() => setReprocessResult(null)}
          />
        )}
        {reprocessError && (
          <ReprocessErrorBanner
            message={reprocessError}
            onDismiss={() => setReprocessError(null)}
          />
        )}

        {/* Metadatos en grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-secondary/30 rounded-lg text-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Recibido</p>
            <p className="mt-0.5 text-foreground/80">{formatDateTime(email.received_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Procesado</p>
            <p className="mt-0.5 text-foreground/80">{formatDateTime(email.processed_at)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Relevancia</p>
            <p className="mt-0.5 text-foreground/80 capitalize">{email.relevance ?? 'media'}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Estado</p>
            <p className="mt-0.5 text-foreground/80 capitalize">{email.status ?? 'pendiente'}</p>
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
            <p className="text-sm text-black leading-relaxed">{email.summary}</p>
          </div>
        )}
      </div>

      {/* Cuerpo del correo */}
      <div className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm">
        <h2 className="text-sm font-bold text-foreground mb-3">Contenido del correo</h2>
        {email.body_plain ? (
          <pre className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap font-sans">
            {email.body_plain}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground italic">No hay contenido disponible</p>
        )}
      </div>

      {/* Borrador de respuesta IA */}
      {suggestedReply && <SuggestedReplyCard reply={suggestedReply} />}

      {/* Clasificación multi-agente */}
      <div className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm">
        <h2 className="text-sm font-bold text-foreground mb-3">Clasificación multi-agente</h2>

        {votes && (
          <div className="space-y-2 mb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Votos de los agentes</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {votes.map((vote) => (
                <div
                  key={vote.agent}
                  className="flex items-center justify-between p-3 rounded-lg bg-secondary/30"
                >
                  <span className="text-xs font-semibold text-muted-foreground uppercase">
                    {METHOD_LABELS[vote.agent] ?? vote.agent}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: CATEGORY_COLORS[vote.category] ?? '#94a3b8' }}
                    />
                    <span className="text-xs font-medium text-foreground/80">
                      {CATEGORY_LABELS[vote.category] ?? vote.category}
                    </span>
                    <span className="text-xs text-muted-foreground font-mono">
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
        <div className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm">
          <h2 className="text-sm font-bold text-foreground mb-3">Historial de clasificaciones</h2>
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
    <div className="flex items-center justify-between px-4 py-2.5 rounded-lg bg-secondary/30">
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
        <span className="text-xs font-medium text-foreground/80 capitalize">
          {CATEGORY_LABELS[entry.category] ?? entry.category}
        </span>
        <span className="text-xs font-mono text-muted-foreground">{formatConfidence(entry.confidence)}</span>
      </div>
      <span className="text-[10px] text-muted-foreground">
        {entry.created_at ? formatDateTime(entry.created_at) : ''}
      </span>
    </div>
  )
}

function SuggestedReplyCard({ reply }: { reply: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(reply).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-foreground">Borrador de respuesta IA</h2>
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
            bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200
            transition-all cursor-pointer"
        >
          {copied ? (
            <>✓ Copiado</>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              Copiar
            </>
          )}
        </button>
      </div>
      <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-lg">
        <pre className="text-sm text-emerald-900 leading-relaxed whitespace-pre-wrap font-sans">
          {reply}
        </pre>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Este borrador fue generado automáticamente por IA. Revísalo antes de enviar.
      </p>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="w-8 h-8 border-4 border-sky-200 border-t-sky-500 rounded-full animate-spin mx-auto" />
        <p className="mt-4 text-sm text-muted-foreground">Cargando correo...</p>
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <p className="text-red-500 font-semibold">Error al cargar</p>
        <p className="text-sm text-muted-foreground mt-1">{message}</p>
      </div>
    </div>
  )
}

function ReprocessSuccessBanner({
  result,
  onDismiss,
}: {
  result: ReprocessResponse
  onDismiss: () => void
}) {
  const catColor = CATEGORY_COLORS[result.category] ?? '#94a3b8'
  const resolutionLabel = RESOLUTION_LABELS[result.resolution] ?? result.resolution

  return (
    <div className="flex items-start gap-3 p-4 rounded-lg bg-emerald-50 border border-emerald-200">
      <svg className="w-5 h-5 mt-0.5 shrink-0 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
        <polyline points="22 4 12 14.01 9 11.01" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-emerald-800">
          Correo re-clasificado
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-xs text-emerald-700">
          <span>
            Categoría:{' '}
            <span className="font-semibold" style={{ color: catColor }}>
              {CATEGORY_LABELS[result.category] ?? result.category}
            </span>
          </span>
          <span>Confianza: <span className="font-semibold">{formatConfidence(result.confidence)}</span></span>
          <span>Resolución: <span className="font-semibold">{resolutionLabel}</span></span>
          <span>Tiempo: <span className="font-semibold">{(result.processing_time_ms / 1000).toFixed(1)}s</span></span>
        </div>
        {result.votes.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {result.votes.map((v) => (
              <span
                key={v.agent}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-white/70 border border-emerald-200"
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[v.category] ?? '#94a3b8' }}
                />
                {METHOD_LABELS[v.agent] ?? v.agent}:{' '}
                {CATEGORY_LABELS[v.category] ?? v.category} ({formatConfidence(v.confidence)})
              </span>
            ))}
          </div>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="shrink-0 p-1 rounded-md text-emerald-400 hover:text-emerald-600 hover:bg-emerald-100 transition-colors cursor-pointer"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  )
}

function ReprocessErrorBanner({
  message,
  onDismiss,
}: {
  message: string
  onDismiss: () => void
}) {
  return (
    <div className="flex items-start gap-3 p-4 rounded-lg bg-red-50 border border-red-200">
      <svg className="w-5 h-5 mt-0.5 shrink-0 text-red-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="15" y1="9" x2="9" y2="15" />
        <line x1="9" y1="9" x2="15" y2="15" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-800">
          Error al reprocesar
        </p>
        <p className="text-xs text-red-600 mt-0.5">{message}</p>
      </div>
      <button
        onClick={onDismiss}
        className="shrink-0 p-1 rounded-md text-red-400 hover:text-red-600 hover:bg-red-100 transition-colors cursor-pointer"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  )
}
