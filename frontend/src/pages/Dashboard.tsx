/**
 * Dashboard principal — KPIs y gráficos del sistema.
 *
 * Muestra: total de correos, correos hoy, contactos por categoría,
 * oportunidades por etapa. Datos obtenidos de /api/v1/dashboard/summary.
 */

import { useEffect, useState } from 'react'
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
  type DashboardSummary,
} from '../services/api'

const COLORS = ['#4fc3f7', '#81c784', '#ffb74d', '#e57373', '#ba68c8', '#fff176']

export default function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-slate-500">Cargando dashboard...</p>
  if (error) return <p className="text-red-500">Error: {error}</p>
  if (!data) return <p className="text-slate-500">Sin datos</p>

  const contactsData = Object.entries(data.contacts_by_category).map(
    ([name, value]) => ({ name, value }),
  )
  const oppsData = Object.entries(data.opportunities_by_stage).map(
    ([name, value]) => ({ name, value }),
  )

  return (
    <div>
      <h2 className="text-2xl font-bold text-slate-900 mb-6">Dashboard</h2>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Total correos" value={data.total_emails} color="#4fc3f7" />
        <KpiCard label="Correos hoy" value={data.emails_today} color="#81c784" />
        <KpiCard label="Categorías" value={contactsData.length} color="#ffb74d" />
        <KpiCard label="Etapas activas" value={oppsData.length} color="#ba68c8" />
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contactos por categoría */}
        <Card title="Contactos por categoría">
          {contactsData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={contactsData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#4fc3f7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState />
          )}
        </Card>

        {/* Oportunidades por etapa */}
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
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState />
          )}
        </Card>
      </div>
    </div>
  )
}

function KpiCard({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div
      className="bg-white rounded-xl p-5 shadow-sm"
      style={{ borderTop: `4px solid ${color}` }}
    >
      <p className="m-0 text-xs font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-3xl font-bold text-slate-900">
        {value}
      </p>
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm">
      <h3 className="m-0 mb-4 text-sm font-semibold text-slate-700">{title}</h3>
      {children}
    </div>
  )
}

function EmptyState() {
  return (
    <p className="text-slate-400 text-center py-8">
      Sin datos disponibles
    </p>
  )
}
