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
      <h2 className="text-2xl font-bold text-slate-900 mb-6">Contactos</h2>

      {/* Filtros */}
      <div className="flex gap-3 items-center mb-6">
        <input
          type="text"
          placeholder="Buscar por nombre o email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-64 px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500"
        />
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg outline-none text-sm"
        >
          <option value="">Todas las categorías</option>
          {CATEGORIES.map(c => (
            <option key={c} value={c}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
        <span className="text-sm text-slate-500">
          {total} contacto{total !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Tabla */}
      {loading ? (
        <p className="text-slate-500">Cargando...</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : contacts.length === 0 ? (
        <EmptyState message="No se encontraron contactos" />
      ) : (
        <>
          <table className="w-full bg-white rounded-xl shadow-sm overflow-hidden">
            <thead>
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200">Nombre</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200">Email</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200">Empresa</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200">Categoría</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200">Correos</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 border-b-2 border-slate-200"></th>
              </tr>
            </thead>
            <tbody>
              {contacts.map(c => (
                <tr key={c.id}>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">{c.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">{c.email}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">{c.company || '-'}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">
                    <CategoryBadge category={c.category} />
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">{c.email_count}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 border-b border-slate-100">
                    <button onClick={() => openDetail(c.id)} className="bg-transparent border-none text-sky-500 cursor-pointer underline text-sm hover:text-sky-600">
                      Ver
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Paginación */}
          {totalPages > 1 && (
            <div className="flex gap-2 justify-center mt-4 items-center">
              <button
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
                className="px-3 py-1.5 border border-slate-300 rounded-lg bg-white cursor-pointer text-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
              >
                ← Anterior
              </button>
              <span className="px-2 py-1.5 text-slate-500 text-sm">
                {page + 1} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => p + 1)}
                className="px-3 py-1.5 border border-slate-300 rounded-lg bg-white cursor-pointer text-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
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
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          onClick={() => setDetailId(null)}
        >
          <div
            className="bg-white rounded-xl p-6 w-[420px] max-w-[90vw] max-h-[80vh] overflow-y-auto shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="m-0 mb-2 text-lg font-semibold text-slate-900">{detail.name}</h3>
            <p className="m-0 mb-4 text-sm text-slate-500">{detail.email}</p>

            <div className="mb-4">
              <InfoRow label="Empresa" value={detail.company} />
              <InfoRow label="Cargo" value={detail.position} />
              <InfoRow label="Teléfono" value={detail.phone} />
              <InfoRow label="Correos intercambiados" value={String(detail.email_count)} />
              <InfoRow label="Primer email" value={detail.first_email_at ? new Date(detail.first_email_at).toLocaleDateString() : '-'} />
              <InfoRow label="Último email" value={detail.last_email_at ? new Date(detail.last_email_at).toLocaleDateString() : '-'} />
            </div>

            <div className="mb-4">
              <label className="block mb-1 text-sm font-semibold text-slate-600">
                Categoría
              </label>
              <select
                value={detail.category}
                onChange={e => changeCategory(detail.id, e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg outline-none text-sm"
              >
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setDetailId(null)}
              className="mt-6 px-4 py-2 bg-slate-100 border-none rounded-lg cursor-pointer text-sm hover:bg-slate-200 text-slate-700"
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
      className="inline-flex px-3 py-1 rounded-full text-xs font-semibold"
      style={{
        background: colors[category] || '#f5f5f5',
        color: textColors[category] || '#888',
      }}
    >
      {category}
    </span>
  )
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-slate-100">
      <span className="text-slate-500 text-sm">{label}</span>
      <span className="text-sm text-slate-700">{value || '-'}</span>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return <p className="text-slate-400 text-center py-12">{message}</p>
}
