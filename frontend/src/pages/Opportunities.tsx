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

  if (loading) return <p>Cargando pipeline...</p>
  if (error) return <p style={{ color: '#d32f2f' }}>Error: {error}</p>

  const totalOpps = Object.values(byStage).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>Pipeline de Oportunidades</h2>
        <button onClick={openCreateForm} style={primaryBtnStyle}>
          + Nueva oportunidad
        </button>
      </div>

      {totalOpps === 0 ? (
        <p style={{ color: '#aaa', textAlign: 'center', padding: '3rem 0' }}>
          No hay oportunidades todavía. ¡Crea la primera!
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${STAGES.length}, 1fr)`,
            gap: '0.75rem',
            alignItems: 'start',
          }}
        >
          {STAGES.map(stage => {
            const items = byStage[stage.key] || []
            return (
              <div key={stage.key} style={{ background: '#fafafa', borderRadius: 10, padding: '0.75rem', minHeight: 200 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.75rem',
                    padding: '0.5rem',
                    background: stage.color,
                    borderRadius: 8,
                    color: '#fff',
                  }}
                >
                  <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{stage.label}</span>
                  <span style={{ fontSize: '0.8rem', opacity: 0.8 }}>{items.length}</span>
                </div>

                {items.map(opp => (
                  <div
                    key={opp.id}
                    onClick={() => openEditForm(opp)}
                    style={{
                      background: '#fff',
                      borderRadius: 8,
                      padding: '0.75rem',
                      marginBottom: '0.5rem',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
                      cursor: 'pointer',
                      borderLeft: `3px solid ${stage.color}`,
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.25rem' }}>
                      {opp.title}
                    </div>
                    {opp.value && (
                      <div style={{ fontSize: '0.85rem', color: '#2e7d32', fontWeight: 600 }}>
                        ${Number(opp.value).toLocaleString()}
                      </div>
                    )}
                    {opp.probability && (
                      <div style={{ fontSize: '0.75rem', color: '#888' }}>
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
    <div style={modalOverlay} onClick={onClose}>
      <div style={modalContent} onClick={e => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 1rem' }}>{title}</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Título *</label>
            <input value={titleVal} onChange={e => setTitleVal(e.target.value)} style={inputStyle} required />
          </div>

          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Contacto *</label>
            <select value={contactId} onChange={e => setContactId(e.target.value)} style={inputStyle} required>
              <option value="">Seleccionar contacto</option>
              {contacts.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.email})</option>
              ))}
            </select>
          </div>

          {stages && (
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={labelStyle}>Etapa</label>
              <select value={stage} onChange={e => { setStage(e.target.value); onStageChange?.(e.target.value) }} style={inputStyle}>
                {stages.map(s => (
                  <option key={s.key} value={s.key}>{s.label}</option>
                ))}
              </select>
            </div>
          )}

          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Descripción</label>
            <textarea value={description} onChange={e => setDescription(e.target.value)} style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }} />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <div>
              <label style={labelStyle}>Valor ($)</label>
              <input type="number" value={value} onChange={e => setValue(e.target.value)} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Probabilidad (%)</label>
              <input type="number" value={probability} onChange={e => setProbability(e.target.value)} style={inputStyle} min={0} max={100} />
            </div>
          </div>

          <div style={{ marginBottom: '0.75rem' }}>
            <label style={labelStyle}>Cierre estimado</label>
            <input type="date" value={expectedClose} onChange={e => setExpectedClose(e.target.value)} style={inputStyle} />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Notas</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }} />
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            {onDelete && (
              <button type="button" onClick={onDelete} style={deleteBtnStyle}>
                Eliminar
              </button>
            )}
            <button type="button" onClick={onClose} style={cancelBtnStyle}>
              Cancelar
            </button>
            <button type="submit" disabled={saving} style={primaryBtnStyle}>
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: '0.25rem',
  fontSize: '0.8rem',
  fontWeight: 600,
  color: '#555',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.5rem 0.65rem',
  border: '1px solid #ddd',
  borderRadius: 6,
  fontSize: '0.9rem',
  outline: 'none',
  boxSizing: 'border-box',
}

const primaryBtnStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  background: '#1a1a2e',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: '0.85rem',
}

const deleteBtnStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  background: '#fff',
  color: '#d32f2f',
  border: '1px solid #d32f2f',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: '0.85rem',
}

const cancelBtnStyle: React.CSSProperties = {
  padding: '0.5rem 1rem',
  background: '#eee',
  border: 'none',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: '0.85rem',
}

const modalOverlay: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.4)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 100,
}

const modalContent: React.CSSProperties = {
  background: '#fff',
  borderRadius: 12,
  padding: '2rem',
  width: 480,
  maxWidth: '90vw',
  maxHeight: '85vh',
  overflowY: 'auto',
  boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
}
