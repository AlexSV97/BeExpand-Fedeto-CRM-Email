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
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="bg-white rounded-xl shadow-2xl p-8 w-96">
        <h1 className="m-0 mb-1 text-2xl font-bold text-slate-900">
          BeExpand CRM
        </h1>
        <p className="m-0 mb-6 text-sm text-slate-500">
          Inicia sesión para continuar
        </p>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-semibold text-slate-600 mb-1">Usuario</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
              placeholder="admin"
              required
              autoFocus
            />
          </div>

          <div className="mb-6">
            <label className="block text-sm font-semibold text-slate-600 mb-1">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
              placeholder="••••••••"
              required
            />
          </div>

          {(localError || error) && (
            <p className="text-red-500 text-sm m-0 mb-4">
              {localError || error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-slate-800 text-white rounded-lg py-2.5 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer text-base font-medium"
          >
            {submitting ? 'Entrando...' : 'Iniciar sesión'}
          </button>
        </form>
      </div>
    </div>
  )
}

