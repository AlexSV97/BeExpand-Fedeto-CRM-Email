/**
 * App — configuración de rutas con React Router.
 *
 * Rutas públicas:
 *   /login → Login
 *
 * Rutas protegidas (requieren token JWT):
 *   /dashboard       → Dashboard (o SocShell si la flag SOC está activa)
 *   /contacts        → Contactos
 *   /opportunities   → Pipeline
 *   /                → Redirige a /dashboard
 *   *                → Redirige a /dashboard
 *
 * Integración SOC shell (Phase 5):
 *   - SocShellProvider envuelve siempre toda la app (no-op cuando
 *     localStorage['soc_shell_enabled'] es false)
 *   - Cuando la flag está activa, /dashboard renderiza <SocShell />
 *     en lugar de <Layout /> con <Dashboard />
 *   - El resto de rutas protegidas siguen usando <Layout /> como antes
 *   - El shell preserva el surface activo vía ?soc=... en la URL
 *   - Comportamiento legacy preservado cuando la flag está OFF
 */

import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { SocShellProvider } from './services/soc/SocShellProvider'
import { isSocShellEnabled } from './config/socShell'
import Layout from './components/Layout'
import { SocShell } from './components/soc'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EmailDetail from './pages/EmailDetail'
import Contacts from './pages/Contacts'
import Opportunities from './pages/Opportunities'
import Invoices from './pages/Invoices'
import Settings from './pages/Settings'

// ── ProtectedRoute: soporta ambos patrones ──
//
//   <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
//     <Route ... />
//   </Route>
//
//   — y —
//
//   <Route element={<ProtectedRoute />}>
//     <Route ... />
//   </Route>

function ProtectedRoute({ children }: { children?: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ padding: '2rem', textAlign: 'center', color: '#888' }}>Cargando sesión...</div>
  if (!user) return <Navigate to="/login" replace />
  if (children) return <>{children}</>
  return <Outlet />
}

// ── AppRoutes: dos modos según la flag SOC ──

function AppRoutes() {
  const socEnabled = isSocShellEnabled()

  if (socEnabled) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          {/*
           * /dashboard usa SocShell (sin Outlet — maneja sus propias
           * superficies mediante zustand + browser history)
           */}
          <Route path="/dashboard" element={<SocShell />} />
          {/*
           * El resto de rutas siguen usando el Layout legacy con Outlet
           * para que el usuario pueda navegar /contacts, /settings, etc.
           * sin salir del shell SOC.
           */}
          <Route element={<Layout />}>
            <Route path="/emails/:id" element={<EmailDetail />} />
            <Route path="/contacts" element={<Contacts />} />
            <Route path="/opportunities" element={<Opportunities />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    )
  }

  // ── Modo legacy (SOC desactivado) — exactamente igual que antes ──

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/emails/:id" element={<EmailDetail />} />
        <Route path="/contacts" element={<Contacts />} />
        <Route path="/opportunities" element={<Opportunities />} />
        <Route path="/invoices" element={<Invoices />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

function DarkModeDetector() {
  useEffect(() => {
    // Siempre dark mode — como el diseño original de v0
    document.documentElement.classList.add('dark')
    document.title = isSocShellEnabled() ? 'Aiuken SOC' : 'BeExpand CRM'
  }, [])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/*
         * SocShellProvider envuelve toda la app.  Cuando la flag está
         * OFF es un pass-through; cuando está ON provee el contexto
         * zustand a SocShell y sus superficies.
         */}
        <SocShellProvider>
          <DarkModeDetector />
          <AppRoutes />
        </SocShellProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
