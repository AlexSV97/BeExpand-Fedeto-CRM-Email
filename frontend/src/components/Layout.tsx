/**
 * Layout principal — top navigation bar + contenido.
 *
 * Inspirado en el diseño premium de v0.app.
 * Barra superior fija con pestañas, sin sidebar.
 */

import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { motion } from 'framer-motion'

// ── Iconos inline ──

function LogoIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )
}

// ── Fondo animado ambiental ──

function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-background via-background to-muted/50" />
      <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-gradient-to-br from-chart-1/5 to-transparent rounded-full blur-3xl animate-float" />
      <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-gradient-to-br from-chart-2/5 to-transparent rounded-full blur-3xl animate-float-delayed" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[1000px] bg-gradient-to-br from-chart-3/3 to-transparent rounded-full blur-3xl animate-float-slow" />
      <div
        className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(to right, currentColor 1px, transparent 1px),
                           linear-gradient(to bottom, currentColor 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }}
      />
    </div>
  )
}

// ── Pestañas de navegación ──

const navTabs = [
  { to: '/dashboard', label: 'Panel', icon: <LogoIcon /> },
  { to: '/contacts', label: 'Contactos' },
  { to: '/opportunities', label: 'Oportunidades' },
  { to: '/settings', label: 'Ajustes' },
]

function Navigation() {
  const { user, logout } = useAuth()

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl"
      style={{ backgroundColor: 'var(--glass)', borderBottom: '1px solid var(--glass-border)' }}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <NavLink to="/dashboard" className="flex items-center gap-3 no-underline">
          <motion.div
            whileHover={{ scale: 1.02 }}
            transition={{ type: "spring", stiffness: 400, damping: 17 }}
            className="flex items-center gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-foreground to-foreground/70 flex items-center justify-center">
              <span className="text-background font-bold text-sm font-display">Bc</span>
            </div>
            <span className="font-semibold text-lg tracking-tight font-display text-foreground">BeConnect</span>
          </motion.div>
        </NavLink>

        {/* Pestañas de navegación */}
        <div className="hidden md:flex items-center gap-1 bg-secondary/50 rounded-full p-1">
          {navTabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                `relative px-5 py-2 text-sm font-medium rounded-full transition-colors no-underline ${
                  isActive
                    ? 'text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-primary rounded-full"
                      transition={{ type: "spring", stiffness: 500, damping: 35 }}
                    />
                  )}
                  <span className="relative z-10">{tab.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>

        {/* Usuario */}
        <div className="flex items-center gap-4">
          <button
            onClick={logout}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            Cerrar sesión
          </button>
          <motion.div
            whileHover={{ scale: 1.1 }}
            className="w-9 h-9 rounded-full bg-gradient-to-br from-chart-1 to-chart-2 flex items-center justify-center text-white font-medium text-sm cursor-pointer shadow-lg shadow-chart-1/20"
          >
            {user?.full_name?.[0] ?? user?.username?.[0] ?? '?'}
          </motion.div>
        </div>
      </div>
    </motion.nav>
  )
}

// ── Componente principal ──

export default function Layout() {
  return (
    <div className="min-h-screen relative">
      <AnimatedBackground />
      <Navigation />
      <main className="pt-16">
        <Outlet />
      </main>
    </div>
  )
}
