// [US-044] Contexte d'authentification web — session JWT (access + refresh token).
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { authApi, clearTokens } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthContextProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(authApi.hasSession)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    function onSessionExpired() {
      setIsAuthenticated(false)
    }
    window.addEventListener('potager:auth:session-expired', onSessionExpired)
    return () => window.removeEventListener('potager:auth:session-expired', onSessionExpired)
  }, [])

  const login = useCallback(async (email, motDePasse) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.login(email, motDePasse)
      setIsAuthenticated(true)
      return true
    } catch (e) {
      setError(e.message)
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const register = useCallback(async (email, motDePasse) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.register(email, motDePasse)
      return true
    } catch (e) {
      setError(e.message)
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated, loading, error, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans AuthContextProvider')
  return ctx
}
