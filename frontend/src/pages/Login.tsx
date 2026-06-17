/**
 * Página de Login — formulario de autenticación JWT.
 *
 * Si ya hay sesión activa, redirige al dashboard automáticamente.
 */

import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const { user, login, error } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  // Si ya está autenticado, ir al dashboard
  if (user) return <Navigate to="/dashboard" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLocalError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/dashboard')
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'No se pudo iniciar sesión')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-sidebar-bg)' }}
    >
      {/* Fondo decorativo */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 rounded-full opacity-10"
          style={{ backgroundColor: 'var(--color-accent)', filter: 'blur(80px)' }}
        />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full opacity-10"
          style={{ backgroundColor: '#6366f1', filter: 'blur(80px)' }}
        />
      </div>

      <div className="relative rounded-2xl p-8 w-96"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.06)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#14b8a6] to-[#0d9488] flex items-center justify-center">
            <span className="text-lg font-bold text-white">Bx</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-white m-0">Aiuken SOC</h1>
            <p className="text-xs m-0" style={{ color: 'var(--color-sidebar-text)' }}>
              Inicia sesión para continuar
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#94a3b8' }}>Usuario</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl text-sm outline-none transition-all duration-150"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: 'white',
              }}
              placeholder="admin"
              required
              autoFocus
              onFocus={e => { e.target.style.borderColor = 'var(--color-accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(20, 184, 166, 0.15)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)'; e.target.style.boxShadow = 'none'; }}
            />
          </div>

          <div className="mb-6">
            <label className="block text-xs font-semibold mb-1.5" style={{ color: '#94a3b8' }}>Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl text-sm outline-none transition-all duration-150"
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                color: 'white',
              }}
              placeholder="••••••••"
              required
              onFocus={e => { e.target.style.borderColor = 'var(--color-accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(20, 184, 166, 0.15)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(255, 255, 255, 0.08)'; e.target.style.boxShadow = 'none'; }}
            />
          </div>

          {(localError || error) && (
            <p className="text-sm m-0 mb-4" style={{ color: 'var(--color-danger)' }}>
              {localError || error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl py-2.5 text-sm font-semibold transition-all duration-150 cursor-pointer active:scale-[0.98]"
            style={{
              backgroundColor: 'var(--color-accent)',
              color: 'white',
              opacity: submitting ? 0.6 : 1,
              cursor: submitting ? 'not-allowed' : 'pointer',
            }}
            onMouseEnter={e => { if (!submitting) e.currentTarget.style.backgroundColor = 'var(--color-accent-hover)'; }}
            onMouseLeave={e => { if (!submitting) e.currentTarget.style.backgroundColor = 'var(--color-accent)'; }}
          >
            {submitting ? 'Entrando...' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}

