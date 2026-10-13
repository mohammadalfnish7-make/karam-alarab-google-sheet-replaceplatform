import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { api, readError } from "./api"
import type { User } from "./types"

type AuthValue = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const response = await api("/api/auth/me")
    if (!response.ok) {
      setUser(null)
      return
    }
    setUser((await response.json()) as User)
  }, [])

  useEffect(() => {
    refresh().finally(() => setLoading(false))
  }, [refresh])

  useEffect(() => {
    const onLost = () => setUser(null)
    window.addEventListener("auth:lost", onLost)
    return () => window.removeEventListener("auth:lost", onLost)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      const error = await readError(response)
      throw new Error(error.message || "Invalid email or password")
    }
    setUser((await response.json()) as User)
  }, [])

  const logout = useCallback(async () => {
    await api("/api/auth/logout", { method: "POST" })
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("AuthProvider is missing")
  return value
}
