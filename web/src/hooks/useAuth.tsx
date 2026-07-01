import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken, setOnAuthExpired } from '@/api/client'
import type { UserInfo } from '@/types'

interface AuthContextValue {
  user: UserInfo | null
  token: string | null
  isAuthenticated: boolean
  isVerifying: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthCtx = createContext<AuthContextValue>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem('auth_token'))
  const [isVerifying, setIsVerifying] = useState(true)
  const navigate = useNavigate()

  const isAuthenticated = !!user && !!token

  // Handle 401 from API — clear auth and redirect
  const handleAuthExpired = useCallback(() => {
    setUser(null)
    setTokenState(null)
    setToken(null)
    navigate('/login')
  }, [navigate])

  useEffect(() => {
    setOnAuthExpired(handleAuthExpired)
  }, [handleAuthExpired])

  // Verify token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token')
    if (!storedToken) {
      setIsVerifying(false)
      return
    }
    setToken(storedToken)
    api.me()
      .then((u) => {
        setUser(u)
        setTokenState(storedToken)
      })
      .catch((err: unknown) => {
        // Only clear token if the error was a genuine 401 (token expired/invalid).
        // Network errors or server 5xx should not log the user out.
        const msg = err instanceof Error ? err.message : ''
        if (msg.includes('登录已过期') || msg.includes('Token')) {
          setToken(null)
          setTokenState(null)
        }
        // Otherwise: user stays "logged in" but token verification failed temporarily.
        // The next API call that needs auth will trigger the 401 handler if needed.
      })
      .finally(() => {
        setIsVerifying(false)
      })
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login({ username, password })
    setToken(res.token)
    setTokenState(res.token)
    setUser(res.user)
  }, [])

  const register = useCallback(async (username: string, password: string) => {
    const res = await api.register({ username, password })
    setToken(res.token)
    setTokenState(res.token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setTokenState(null)
    setUser(null)
    navigate('/login')
  }, [navigate])

  return (
    <AuthCtx.Provider value={{ user, token, isAuthenticated, isVerifying, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  return useContext(AuthCtx)
}
