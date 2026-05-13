/**
 * Vista de Contactos — lista paginada con búsqueda y filtro por categoría.
 *
 * Acciones: ver detalle, cambiar categoría (PATCH).
 */

import { useEffect, useState, useCallback } from 'react'
import {
  getContacts,
  getContact,
  updateContact,
  type ContactResponse,
} from '../services/api'

const CATEGORIES = ['cliente', 'lead', 'proveedor', 'otro', 'pendiente']

export default function Contacts() {
  const [contacts, setContacts] = useState<ContactResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filtros
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  // Detalle
  const [detailId, setDetailId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ContactResponse | null>(null)
  const fetchContacts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getContacts({
        search: search || undefined,
        category: category || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      setContacts(res.items)
      setTotal(res.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar contactos')
    } finally {
      setLoading(false)
    }
  }, [search, category, page])

  useEffect(() => {
    fetchContacts()
  }, [fetchContacts])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  async function openDetail(id: string) {
    setDetailId(id)
    try {
      const c = await getContact(id)
      setDetail(c)
    } catch {
      setDetail(null)
    }
  }

  async function changeCategory(id: string, newCategory: string) {
    try {
      await updateContact(id, { category: newCategory })
      // Refrescar detalle y lista
      if (detailId === id) {
        const updated = await getContact(id)
        setDetail(updated)
      }
      fetchContacts()
    } catch {
      // Silencioso
    }
  }

  // Resetear página al cambiar filtros
  useEffect(() => {
    setPage(0)
  }, [search, category])

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Contactos</h2>

      {/* Filtros */}
      <div
        style={{
          display: 'flex',
          gap: '0.75rem',
          marginBottom: '1.5rem',
          alignItems: 'center',
        }}
      >
        <input
          type="text"
          placeholder="Buscar por nombre o email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={filterInputStyle}
        />
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          style={filterInputStyle}
        >
          <option value="">Todas las categorías</option>
          {CATEGORIES.map(c => (
            <option key={c} value={c}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
        <span style={{ fontSize: '0.85rem', color: '#888' }}>
          {total} contacto{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Tabla */}
      {loading ? (
        <p>Cargando...</p>
      ) : error ? (
        <p style={{ color: '#d32f2f' }}>{error}</p>
      ) : contacts.length === 0 ? (
        <EmptyState message="No se encontraron contactos" />
      ) : (
        <>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Nombre</th>
                <th style={thStyle}>Email</th>
                <th style={thStyle}>Empresa</th>
                <th style={thStyle}>Categoría</th>
                <th style={thStyle}>Correos</th>
                <th style={thStyle}></th>
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => (
                <tr key={c.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={tdStyle}>{c.name}</td>
                  <td style={tdStyle}>{c.email}</td>
                  <td style={tdStyle}>{c.company || '-'}</td>
                  <td style={tdStyle}>
                    <CategoryBadge category={c.category} />
                  </td>
                  <td style={tdStyle}>{c.email_count}</td>
                  <td style={tdStyle}>
                    <button onClick={() => openDetail(c.id)} style={linkStyle}>
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Paginación */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', marginTop: '1rem' }}>
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
                style={pageBtnStyle}
              >
                ← Anterior
              </button>
              <span style={{ padding: '0.5rem', color: '#888' }}>
                {page + 1} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
                style={pageBtnStyle}
              >
                Siguiente →
              </button>
            </div>
          )}
        </>
      )}

      {/* Modal detalle */}
      {detailId && detail && (
        <div
          style={modalOverlay}
          onClick={() => setDetailId(null)}
        >
          <div
            style={modalContent}
            onClick={e => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 0.5rem' }}>{detail.name}</h3>
            <p style={{ margin: '0 0 1rem', color: '#888' }}>{detail.email}</p>

            <div style={{ marginBottom: '1rem' }}>
              <InfoRow label="Empresa" value={detail.company} />
              <InfoRow label="Cargo" value={detail.position} />
              <InfoRow label="Teléfono" value={detail.phone} />
              <InfoRow label="Correos intercambiados" value={String(detail.email_count)} />
              <InfoRow label="Primer email" value={detail.first_email_at ? new Date(detail.first_email_at).toLocaleDateString() : '-'} />
              <InfoRow label="Último email" value={detail.last_email_at ? new Date(detail.last_email_at).toLocaleDateString() : '-'} />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '0.35rem', fontSize: '0.85rem', fontWeight: 600, color: '#555' }}>
                Categoría
              </label>
              <select
                value={detail.category}
                onChange={e => changeCategory(detail.id, e.target.value)}
                style={filterInputStyle}
              >
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setDetailId(null)}
              style={{
                marginTop: '1.5rem',
                padding: '0.5rem 1rem',
                background: '#eee',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function CategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    cliente: '#e3f2fd',
    lead: '#e8f5e9',
    proveedor: '#fff3e0',
    otro: '#f3e5f5',
    pendiente: '#f5f5f5',
  }
  const textColors: Record<string, string> = {
    cliente: '#1565c0',
    lead: '#2e7d32',
    proveedor: '#e65100',
    otro: '#6a1b9a',
    pendiente: '#888',
  }
  return (
    <span
      style={{
        background: colors[category] || '#f5f5f5',
        color: textColors[category] || '#888',
        padding: '0.2rem 0.6rem',
        borderRadius: 12,
        fontSize: '0.8rem',
        fontWeight: 600,
      }}
    >
      {category}
    </span>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.35rem 0', borderBottom: '1px solid #f0f0f0' }}>
      <span style={{ color: '#888', fontSize: '0.85rem' }}>{label}</span>
      <span style={{ fontSize: '0.9rem' }}>{value || '-'}</span>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return <p style={{ color: '#aaa', textAlign: 'center', padding: '3rem 0' }}>{message}</p>
}

const filterInputStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  border: '1px solid #ddd',
  borderRadius: 8,
  fontSize: '0.9rem',
  outline: 'none',
}

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  background: '#fff',
  borderRadius: 10,
  overflow: 'hidden',
  boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.75rem 1rem',
  fontSize: '0.8rem',
  color: '#888',
  textTransform: 'uppercase',
  letterSpacing: 1,
  borderBottom: '2px solid #eee',
}

const tdStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  fontSize: '0.9rem',
}

const linkStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#4fc3f7',
  cursor: 'pointer',
  textDecoration: 'underline',
  fontSize: '0.85rem',
}

const pageBtnStyle: React.CSSProperties = {
  padding: '0.4rem 0.8rem',
  border: '1px solid #ddd',
  borderRadius: 6,
  background: '#fff',
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
  width: 420,
  maxWidth: '90vw',
  maxHeight: '80vh',
  overflowY: 'auto',
  boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
}
