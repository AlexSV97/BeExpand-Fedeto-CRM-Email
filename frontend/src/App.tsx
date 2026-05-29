/**
 * App — configuración de rutas con React Router.
 *
 * Rutas públicas:
 *   /login → Login
 *
 * Rutas protegidas (requieren token JWT):
 *   /dashboard       → Dashboard
 *   /contacts        → Contactos
 *   /opportunities   → Pipeline
 *   /                → Redirige a /dashboard
 *   *                → Redirige a /dashboard
 */

import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EmailDetail from './pages/EmailDetail'
import Contacts from './pages/Contacts'
import Opportunities from './pages/Opportunities'
import Invoices from './pages/Invoices'
import Settings from './pages/Settings'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ padding: '2rem', textAlign: 'center', color: '#888' }}>Cargando sesión...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
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
    document.documentElement.classList.add("dark");
  }, []);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <DarkModeDetector />
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
