import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { clearTokens, fetchMe, isAuthenticated, refreshAccessToken } from '../services/api'
import type { UserInfo } from '../types/api'

interface AuthContextType {
  authed: boolean
  user: UserInfo | null
  loading: boolean
  loadUser: () => Promise<UserInfo>
  clearAuth: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(false)
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    const me = await fetchMe()
    setUser(me)
    setAuthed(true)
    return me
  }, [])

  const clearAuth = useCallback(() => {
    clearTokens()
    setAuthed(false)
    setUser(null)
  }, [])

  useEffect(() => {
    async function restore() {
      const ok = isAuthenticated() || await refreshAccessToken()
      if (!ok) {
        clearAuth()
        setLoading(false)
        return
      }
      try {
        await loadUser()
      } catch (error) {
        void error
        clearAuth()
      } finally {
        setLoading(false)
      }
    }
    restore()
  }, [clearAuth, loadUser])

  return (
    <AuthContext.Provider value={{ authed, user, loading, loadUser, clearAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
