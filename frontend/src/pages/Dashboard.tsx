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

  if (loading) return <p>Cargando dashboard...</p>
  if (error) return <p style={{ color: '#d32f2f' }}>Error: {error}</p>
  if (!data) return <p>Sin datos</p>

  const contactsData = Object.entries(data.contacts_by_category).map(
    ([name, value]) => ({ name, value }),
  )
  const oppsData = Object.entries(data.opportunities_by_stage).map(
    ([name, value]) => ({ name, value }),
  )

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Dashboard</h2>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
        <KpiCard label="Total correos" value={data.total_emails} color="#4fc3f7" />
        <KpiCard label="Correos hoy" value={data.emails_today} color="#81c784" />
        <KpiCard label="Categorías" value={contactsData.length} color="#ffb74d" />
        <KpiCard label="Etapas activas" value={oppsData.length} color="#ba68c8" />
      </div>

      {/* Gráficos */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
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
      style={{
        background: '#fff',
        borderRadius: 10,
        padding: '1.25rem',
        borderTop: `4px solid ${color}`,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      <p style={{ margin: 0, fontSize: '0.8rem', color: '#888', textTransform: 'uppercase', letterSpacing: 1 }}>
        {label}
      </p>
      <p style={{ margin: '0.5rem 0 0', fontSize: '2rem', fontWeight: 700, color: '#1a1a2e' }}>
        {value}
      </p>
    </div>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 10,
        padding: '1.25rem',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem', color: '#555' }}>{title}</h3>
      {children}
    </div>
  )
}

function EmptyState() {
  return (
    <p style={{ color: '#aaa', textAlign: 'center', padding: '2rem 0' }}>
      Sin datos disponibles
    </p>
  )
}
