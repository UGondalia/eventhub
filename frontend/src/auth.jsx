import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, getToken, setToken } from './api'
import * as cognito from './cognito'

// One interface, two sign-in back ends:
//   local (default)  the Python /auth endpoints, JWT kept in localStorage
//   Amazon Cognito   chosen automatically when VITE_COGNITO_* are set at build time
// The rest of the app only uses { user, login, signup, confirm, resendCode, logout }.
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(cognito.enabled || Boolean(getToken()))

  useEffect(() => {
    if (cognito.enabled) {
      cognito
        .getIdToken()
        .then((token) => token && setUser(cognito.userFromToken(token)))
        .finally(() => setLoading(false))
      return
    }
    if (!getToken()) return
    api
      .me()
      .then((res) => setUser(res.user))
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    if (cognito.enabled) {
      const next = cognito.userFromToken(await cognito.signIn(email, password))
      setUser(next)
      return next
    }
    const res = await api.login({ email, password })
    setToken(res.token)
    setUser(res.user)
    return res.user
  }, [])

  // Local sign-up signs you in at once. Cognito emails a code first, so it returns needsConfirm.
  const signup = useCallback(async (name, email, password) => {
    if (cognito.enabled) {
      await cognito.signUp(name, email, password)
      return { needsConfirm: true }
    }
    const res = await api.signup({ name, email, password })
    setToken(res.token)
    setUser(res.user)
    return { user: res.user }
  }, [])

  const confirm = useCallback(async (email, code, password) => {
    await cognito.confirmSignUp(email, code)
    return login(email, password)
  }, [login])

  const logout = useCallback(() => {
    if (cognito.enabled) cognito.signOut()
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user, loading, login, signup, confirm, logout,
      resendCode: cognito.resendCode,
      cognitoEnabled: cognito.enabled,
      isAdmin: user?.role === 'admin',
    }),
    [user, loading, login, signup, confirm, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
