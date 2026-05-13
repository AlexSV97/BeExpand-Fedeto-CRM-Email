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
    } catch {
      setLocalError('Credenciales inválidas')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#1a1a2e',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '2.5rem',
          width: 360,
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
        }}
      >
        <h1 style={{ margin: '0 0 0.25rem', fontSize: '1.5rem', color: '#1a1a2e' }}>
          BeExpand CRM
        </h1>
        <p style={{ margin: '0 0 1.5rem', color: '#888', fontSize: '0.9rem' }}>
          Inicia sesión para continuar
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Usuario</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              style={inputStyle}
              placeholder="admin"
              required
              autoFocus
            />
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={labelStyle}>Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={inputStyle}
              placeholder="••••••••"
              required
            />
          </div>

          {(localError || error) && (
            <p style={{ color: '#d32f2f', fontSize: '0.85rem', margin: '0 0 1rem' }}>
              {localError || error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: submitting ? '#888' : '#1a1a2e',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: '1rem',
              cursor: submitting ? 'not-allowed' : 'pointer',
            }}
          >
            {submitting ? 'Entrando...' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: '0.35rem',
  fontSize: '0.85rem',
  fontWeight: 600,
  color: '#555',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.65rem 0.75rem',
  border: '1px solid #ddd',
  borderRadius: 8,
  fontSize: '0.95rem',
  outline: 'none',
  boxSizing: 'border-box',
}
