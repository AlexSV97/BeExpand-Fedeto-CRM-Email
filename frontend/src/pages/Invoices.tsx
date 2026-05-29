/**
 * Facturas — listado de facturas extraídas de adjuntos de email.
 *
 * Muestra las facturas detectadas automáticamente con datos extraídos
 * (proveedor, importe, fecha, vencimiento). Permite descargar el PDF.
 */

import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  getInvoices,
  getInvoiceDownloadUrl,
  type InvoiceResponse,
} from '../services/api'

export default function Invoices() {
  const [invoices, setInvoices] = useState<InvoiceResponse[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filtros
  const [proveedorFilter, setProveedorFilter] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 20

  const fetchInvoices = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await getInvoices({
        proveedor: proveedorFilter || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      setInvoices(res.invoices)
      setTotal(res.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar facturas')
    } finally {
      setLoading(false)
    }
  }, [proveedorFilter, page])

  useEffect(() => {
    fetchInvoices()
  }, [fetchInvoices])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  function formatImporte(val: number | null): string {
    if (val === null || val === undefined) return '—'
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: 'EUR',
    }).format(val)
  }

  function formatFecha(val: string | null): string {
    if (!val) return '—'
    try {
      const d = new Date(val)
      return d.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    } catch {
      return val
    }
  }

  function getStatusIcon(inv: InvoiceResponse): string {
    if (inv.numero && inv.importe) return '✅'
    if (inv.numero) return '📄'
    return '📎'
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Facturas</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {total} factura{total !== 1 ? 's' : ''} extraída{total !== 1 ? 's' : ''} de adjuntos de email
            </p>
          </div>
        </div>

        {/* Filtros */}
        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Filtrar por proveedor..."
            value={proveedorFilter}
            onChange={(e) => {
              setProveedorFilter(e.target.value)
              setPage(0)
            }}
            className="px-4 py-2 rounded-xl bg-secondary/50 border border-border/50 text-sm
                       focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all w-64"
          />
        </div>

        {/* Tabla */}
        <div className="rounded-2xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center text-muted-foreground">Cargando facturas...</div>
          ) : error ? (
            <div className="p-12 text-center text-red-500">{error}</div>
          ) : invoices.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground">
              <p className="text-lg mb-2">No hay facturas aún</p>
              <p className="text-sm">
                Las facturas aparecerán aquí automáticamente cuando se procesen correos con facturas adjuntas.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="text-left px-6 py-4 font-medium w-10"></th>
                    <th className="text-left px-6 py-4 font-medium">Proveedor</th>
                    <th className="text-left px-6 py-4 font-medium">Nº Factura</th>
                    <th className="text-right px-6 py-4 font-medium">Importe</th>
                    <th className="text-left px-6 py-4 font-medium">Fecha</th>
                    <th className="text-left px-6 py-4 font-medium">Vencimiento</th>
                    <th className="text-center px-6 py-4 font-medium">Descargar</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv, idx) => (
                    <motion.tr
                      key={inv.id}
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.03 }}
                      className="border-b border-border/25 hover:bg-secondary/30 transition-colors"
                    >
                      <td className="px-6 py-4 text-lg">{getStatusIcon(inv)}</td>
                      <td className="px-6 py-4 font-medium">
                        {inv.proveedor || '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground font-mono">
                        {inv.numero || '—'}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold tabular-nums">
                        {formatImporte(inv.importe)}
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {formatFecha(inv.fecha)}
                      </td>
                      <td className={`px-6 py-4 text-sm ${
                        inv.vencimiento ? 'text-muted-foreground' : ''
                      }`}>
                        {formatFecha(inv.vencimiento)}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <a
                          href={getInvoiceDownloadUrl(inv.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                                     bg-primary/10 text-primary text-sm font-medium
                                     hover:bg-primary/20 transition-colors no-underline"
                          title="Descargar PDF"
                        >
                          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                            <polyline points="7 10 12 15 17 10" />
                            <line x1="12" y1="15" x2="12" y2="3" />
                          </svg>
                          PDF
                        </a>
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Paginación */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-4 py-2 rounded-xl bg-secondary/50 text-sm disabled:opacity-30
                         hover:bg-secondary transition-colors cursor-pointer"
            >
              ← Anterior
            </button>
            <span className="text-sm text-muted-foreground px-3">
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-4 py-2 rounded-xl bg-secondary/50 text-sm disabled:opacity-30
                         hover:bg-secondary transition-colors cursor-pointer"
            >
              Siguiente →
            </button>
          </div>
        )}
      </motion.div>
    </div>
  )
}
