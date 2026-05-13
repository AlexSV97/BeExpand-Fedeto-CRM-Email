/**
 * AuthContext — gestión de sesión JWT en toda la app.
 *
 * Provee: login, logout, usuario actual, estado de autenticación.
 * Persiste el token en localStorage para que sobreviva al refresh.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import {
  login as apiLogin,
  getMe,
  setToken,
  getToken,
  type UserResponse,
} from '../services/api'

interface AuthContextType {
  user: UserResponse | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Al montar, recuperar sesión del token guardado
  useEffect(() => {
    const token = getToken()
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          // Token inválido/expirado — limpiar
          setToken(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    setError(null)
    try {
      const res = await apiLogin({ username, password })
      setToken(res.access_token)
      const me = await getMe()
      setUser(me)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error de conexión')
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}

/**
 * Hook para proteger páginas que requieren autenticación.
 * Retorna true/false y redirige si no hay sesión.
 */
export function useRequireAuth(): boolean {
  const { user, loading } = useAuth()
  return loading || !!user
}
