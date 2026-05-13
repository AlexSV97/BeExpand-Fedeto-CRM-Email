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
    <div style={{ display: 'flex', minHeight: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Sidebar */}
      <nav
        style={{
          width: 240,
          background: '#1a1a2e',
          color: '#eee',
          padding: '1.5rem 0',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ padding: '0 1.5rem 1.5rem', borderBottom: '1px solid #333', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>BeExpand CRM</h2>
          <span style={{ fontSize: '0.8rem', color: '#888' }}>{user?.username}</span>
        </div>

        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem 1.5rem',
              color: isActive ? '#fff' : '#aaa',
              background: isActive ? '#16213e' : 'transparent',
              textDecoration: 'none',
              borderLeft: isActive ? '3px solid #4fc3f7' : '3px solid transparent',
              fontWeight: isActive ? 600 : 400,
            })}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}

        <div style={{ marginTop: 'auto', padding: '1rem 1.5rem' }}>
          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              padding: '0.5rem',
              background: 'transparent',
              border: '1px solid #555',
              borderRadius: 6,
              color: '#ccc',
              cursor: 'pointer',
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </nav>

      {/* Contenido */}
      <main style={{ flex: 1, background: '#f5f5f5', padding: '2rem', overflowY: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
