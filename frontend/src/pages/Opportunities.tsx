/**
 * Pipeline de Oportunidades — vista kanban por etapas.
 *
 * Muestra oportunidades agrupadas por etapa. Incluye crear nueva,
 * editar, cambiar etapa, y eliminar.
 */

import { useEffect, useState, useCallback } from 'react'
import {
  getOpportunities,
  createOpportunity,
  updateOpportunity,
  deleteOpportunity,
  getContacts,
  type OpportunityResponse,
  type OpportunityCreate,
  type ContactResponse,
} from '../services/api'

const STAGES = [
  { key: 'nueva', label: 'Nueva', color: '#4fc3f7' },
  { key: 'calificada', label: 'Calificada', color: '#81c784' },
  { key: 'propuesta', label: 'Propuesta', color: '#ffb74d' },
  { key: 'negociacion', label: 'Negociación', color: '#ba68c8' },
  { key: 'cerrada_ganada', label: 'Ganada', color: '#2e7d32' },
  { key: 'cerrada_perdida', label: 'Perdida', color: '#e57373' },
]

export default function Opportunities() {
  const [byStage, setByStage] = useState<Record<string, OpportunityResponse[]>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Modal
  const [editing, setEditing] = useState<OpportunityResponse | null>(null)
  const [creating, setCreating] = useState(false)
  const [contacts, setContacts] = useState<ContactResponse[]>([])

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getOpportunities({ limit: 200 })
      const grouped: Record<string, OpportunityResponse[]> = {}
      for (const s of STAGES) grouped[s.key] = []
      for (const opp of res.items) {
        if (grouped[opp.stage]) grouped[opp.stage].push(opp)
        else grouped[opp.stage] = [opp]
      }
      setByStage(grouped)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  async function handleCreate(data: OpportunityCreate) {
    await createOpportunity(data)
    setCreating(false)
    fetchAll()
  }

  async function handleUpdate(id: string, data: OpportunityCreate) {
    await updateOpportunity(id, data)
    setEditing(null)
    fetchAll()
  }

  async function handleDelete(id: string) {
    if (!confirm('¿Eliminar esta oportunidad?')) return
    await deleteOpportunity(id)
    setEditing(null)
    fetchAll()
  }

  async function handleStageChange(id: string, newStage: string) {
    // Buscar datos actuales para no perder campos
    const current = Object.values(byStage).flat().find(o => o.id === id)
    if (!current) return
    await updateOpportunity(id, {
      contact_id: current.contact_id,
      title: current.title,
      stage: newStage,
      description: current.description ?? undefined,
      value: current.value ?? undefined,
      probability: current.probability ?? undefined,
      expected_close: current.expected_close ?? undefined,
      notes: current.notes ?? undefined,
    })
    fetchAll()
  }

  async function openEditForm(opp: OpportunityResponse) {
    const res = await getContacts({ limit: 100 })
    setContacts(res.items)
    setEditing(opp)
  }

  async function openCreateForm() {
    const res = await getContacts({ limit: 100 })
    setContacts(res.items)
    setCreating(true)
  }

  if (loading) return <p className="text-slate-500">Cargando pipeline...</p>
  if (error) return <p className="text-red-500">Error: {error}</p>

  const totalOpps = Object.values(byStage).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="m-0 text-2xl font-bold text-slate-900">Pipeline de Oportunidades</h2>
        <button onClick={openCreateForm} className="bg-slate-800 text-white px-4 py-2 rounded-lg hover:bg-slate-700 text-sm font-medium cursor-pointer">
          + Nueva oportunidad
        </button>
      </div>

      {totalOpps === 0 ? (
        <p className="text-slate-400 text-center py-12">
          No hay oportunidades todavía. ¡Crea la primera!
        </p>
      ) : (
        <div className="grid grid-cols-6 gap-3 items-start">
          {STAGES.map(stage => {
            const items = byStage[stage.key] || []
            return (
              <div key={stage.key} className="bg-slate-100 rounded-xl p-3 min-h-[200px]">
                <div
                  className="flex justify-between items-center mb-2 px-3 py-2 rounded-lg text-white text-sm font-semibold"
                  style={{ background: stage.color }}
                >
                  <span>{stage.label}</span>
                  <span className="text-xs opacity-80">{items.length}</span>
                </div>

                {items.map(opp => (
                  <div
                    key={opp.id}
                    onClick={() => openEditForm(opp)}
                    className="bg-white rounded-lg p-3 mb-2 shadow-sm cursor-pointer border-l-4 hover:shadow-md transition-shadow"
                    style={{ borderLeftColor: stage.color }}
                  >
                    <div className="font-semibold text-sm text-slate-900 mb-1">
                      {opp.title}
                    </div>
                    {opp.value && (
                      <div className="text-sm font-semibold text-green-600">
                        ${Number(opp.value).toLocaleString()}
                      </div>
                    )}
                    {opp.probability && (
                      <div className="text-xs text-slate-500">
                        {opp.probability}% probabilidad
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}

      {/* Modal crear */}
      {creating && (
        <OppFormModal
          title="Nueva oportunidad"
          contacts={contacts}
          onSave={handleCreate}
          onClose={() => setCreating(false)}
        />
      )}

      {/* Modal editar */}
      {editing && (
        <OppFormModal
          title="Editar oportunidad"
          contacts={contacts}
          initial={editing}
          stages={STAGES}
          onSave={data => handleUpdate(editing.id, data)}
          onDelete={() => handleDelete(editing.id)}
          onStageChange={(newStage) => handleStageChange(editing.id, newStage)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}

// ── Modal Form ──

function OppFormModal({
  title,
  contacts,
  initial,
  stages,
  onSave,
  onDelete,
  onStageChange,
  onClose,
}: {
  title: string
  contacts: ContactResponse[]
  initial?: OpportunityResponse
  stages?: { key: string; label: string; color: string }[]
  onSave: (data: OpportunityCreate) => Promise<void>
  onDelete?: () => Promise<void>
  onStageChange?: (stage: string) => void
  onClose: () => void
}) {
  const [contactId, setContactId] = useState(initial?.contact_id || '')
  const [titleVal, setTitleVal] = useState(initial?.title || '')
  const [description, setDescription] = useState(initial?.description || '')
  const [stage, setStage] = useState(initial?.stage || 'nueva')
  const [value, setValue] = useState(initial?.value ? String(initial.value) : '')
  const [probability, setProbability] = useState(
    initial?.probability ? String(initial.probability) : '',
  )
  const [expectedClose, setExpectedClose] = useState(
    initial?.expected_close || '',
  )
  const [notes, setNotes] = useState(initial?.notes || '')
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await onSave({
        contact_id: contactId,
        title: titleVal,
        description: description || undefined,
        stage: initial ? undefined : stage,
        value: value ? Number(value) : undefined,
        probability: probability ? Number(probability) : undefined,
        expected_close: expectedClose || undefined,
        notes: notes || undefined,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 w-[480px] max-w-[90vw] max-h-[85vh] overflow-y-auto shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="m-0 mb-4 text-lg font-semibold text-slate-900">{title}</h3>
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Título *</label>
            <input value={titleVal} onChange={e => setTitleVal(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500" required />
          </div>

          <div className="mb-3">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Contacto *</label>
            <select value={contactId} onChange={e => setContactId(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500" required>
              <option value="">Seleccionar contacto</option>
              {contacts.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.email})</option>
              ))}
            </select>
          </div>

          {stages && (
            <div className="mb-3">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Etapa</label>
              <select value={stage} onChange={e => { setStage(e.target.value); onStageChange?.(e.target.value) }} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500">
                {stages.map(s => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </div>
          )}

          <div className="mb-3">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Descripción</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 min-h-[60px] resize-y" />
          </div>

          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Valor ($)</label>
              <input type="number" value={value} onChange={e => setValue(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Probabilidad (%)</label>
              <input type="number" value={probability} onChange={e => setProbability(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500" min={0} max={100} />
            </div>
          </div>

          <div className="mb-3">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Cierre estimado</label>
            <input type="date" value={expectedClose} onChange={e => setExpectedClose(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500" />
          </div>

          <div className="mb-4">
            <label className="block text-xs font-semibold text-slate-600 mb-1">Notas</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 min-h-[60px] resize-y" />
          </div>

          <div className="flex gap-2 justify-end">
            {onDelete && (
              <button type="button" onClick={onDelete} className="px-4 py-2 bg-white text-red-500 border border-red-500 rounded-lg cursor-pointer text-sm hover:bg-red-50">
                Eliminar
              </button>
            )}
            <button type="button" onClick={onClose} className="px-4 py-2 bg-slate-100 border-none rounded-lg cursor-pointer text-sm hover:bg-slate-200 text-slate-700">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="px-4 py-2 bg-slate-800 text-white border-none rounded-lg cursor-pointer text-sm font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed">
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

