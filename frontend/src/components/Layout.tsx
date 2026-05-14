/**
 * Layout principal — sidebar de navegación + contenido.
 *
 * Se muestra después del login. Contiene:
 * - Sidebar con links a Dashboard, Contactos, Oportunidades
 * - Header con nombre de usuario y botón de cerrar sesión
 * - Área de contenido para las páginas
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/contacts', label: 'Contactos', icon: '👥' },
  { to: '/opportunities', label: 'Oportunidades', icon: '📈' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <nav className="w-60 bg-slate-900 text-slate-400 py-6 flex flex-col min-h-screen">
        <div className="px-6 pb-6 border-b border-slate-700 mb-4">
          <h2 className="m-0 text-lg text-white">BeExpand CRM</h2>
          <span className="text-xs text-slate-400">{user?.username}</span>
        </div>

        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 px-6 py-3 no-underline border-l-4 transition-colors',
                isActive
                  ? 'bg-slate-800 text-white border-sky-500 font-semibold'
                  : 'bg-transparent text-slate-400 border-transparent hover:bg-slate-800 hover:text-white',
              )
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}

        <div className="mt-auto px-6 py-4">
          <button
            onClick={handleLogout}
            className="w-full py-2 bg-transparent border border-slate-600 rounded-lg text-slate-300 hover:bg-slate-800 cursor-pointer text-sm"
          >
            Cerrar sesión
          </button>
        </div>
      </nav>

      {/* Contenido */}
      <main className="flex-1 bg-slate-50 p-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
