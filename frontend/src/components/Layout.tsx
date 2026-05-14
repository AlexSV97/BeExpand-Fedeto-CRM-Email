/**
 * Layout principal — sidebar de navegación + contenido.
 *
 * Se muestra después del login. Contiene:
 * - Sidebar con navegación e iconos SVG
 * - Header con breadcrumb y usuario
 * - Área de contenido para las páginas
 */

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { cn } from '../lib/utils'

// ── Iconos SVG inline ──

function IconDashboard() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  )
}

function IconContacts() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  )
}

function IconOpportunities() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15V5H3v10" />
      <path d="M3 19h18" />
      <path d="M12 15v-2" />
      <path d="M9 11v2" />
      <path d="M15 11v2" />
      <path d="M7 15h10l-1-4H8l-1 4z" />
    </svg>
  )
}

function IconLogout() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  )
}

// ── Navegación ──

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: <IconDashboard /> },
  { to: '/contacts', label: 'Contactos', icon: <IconContacts /> },
  { to: '/opportunities', label: 'Oportunidades', icon: <IconOpportunities /> },
]

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/contacts': 'Contactos',
  '/opportunities': 'Oportunidades',
}

// ── Componente principal ──

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const pageTitle = pageTitles[location.pathname] ?? ''

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <nav className="w-60 bg-slate-900 flex flex-col min-h-screen shrink-0">
        {/* Logo / Marca */}
        <div className="px-6 py-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center">
              <span className="text-sm font-bold text-white">BC</span>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white leading-tight">BeExpand CRM</h2>
              <span className="text-xs text-slate-500">{user?.username}</span>
            </div>
          </div>
        </div>

        {/* Navegación */}
        <div className="flex-1 py-4 space-y-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg no-underline text-sm transition-all duration-150',
                  isActive
                    ? 'bg-sky-500/10 text-sky-400 font-semibold'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200',
                )
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>

        {/* Cerrar sesión */}
        <div className="px-3 py-4 border-t border-slate-800">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-all duration-150 cursor-pointer"
          >
            <IconLogout />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </nav>

      {/* Área de contenido */}
      <div className="flex-1 flex flex-col min-h-screen bg-slate-50">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="text-slate-300">/</span>
              <span className="text-slate-900 font-medium">{pageTitle}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 rounded-full bg-sky-100 flex items-center justify-center">
                <span className="text-xs font-semibold text-sky-600">
                  {user?.full_name?.[0] ?? user?.username?.[0] ?? '?'}
                </span>
              </div>
              <span className="text-sm text-slate-600">{user?.full_name ?? user?.username}</span>
            </div>
          </div>
        </header>

        {/* Main */}
        <main className="flex-1 p-8 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
