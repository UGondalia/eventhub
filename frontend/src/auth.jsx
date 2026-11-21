import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken } from './api'

// Auth provider.
// Local mode: talks to the Python /auth endpoints and keeps a JWT in localStorage.
// When we move to AWS this is the single file that changes: replace login/signup/logout
// with Amazon Cognito (amazon-cognito-identity-js) and keep the same `user` shape.
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return
    api
      .me()
      .then((res) => setUser(res.user))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await api.login({ email, password })
    setToken(res.token)
    setUser(res.user)
    return res.user
  }, [])

  const signup = useCallback(async (name, email, password) => {
    const res = await api.signup({ name, email, password })
    setToken(res.token)
    setUser(res.user)
    return res.user
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, signup, logout, isAdmin: user?.role === 'admin' }),
    [user, loading, login, signup, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
