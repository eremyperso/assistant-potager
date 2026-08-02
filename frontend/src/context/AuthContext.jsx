// [US-044] Contexte d'authentification web — session JWT (access + refresh token).
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { authApi, clearTokens } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthContextProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(authApi.hasSession)
  const [error, setError] = useState(null)
  const [errorCode, setErrorCode] = useState(null)
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
    setErrorCode(null)
    try {
      await authApi.login(email, motDePasse)
      setIsAuthenticated(true)
      return true
    } catch (e) {
      setError(e.message)
      setErrorCode(e.code || null)
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const register = useCallback(async (email, motDePasse) => {
    setLoading(true)
    setError(null)
    setErrorCode(null)
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

  // [CA12] Renvoie un e-mail de vérification — réponse toujours générique côté API
  const resendVerification = useCallback(async (email) => {
    setLoading(true)
    try {
      await authApi.resendVerification(email)
      return true
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, loading, error, errorCode, login, register, logout, resendVerification }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans AuthContextProvider')
  return ctx
}
