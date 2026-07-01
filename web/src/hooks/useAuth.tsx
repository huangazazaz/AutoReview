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
      .catch(() => {
        // Token invalid — clear it
        setToken(null)
        setTokenState(null)
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
