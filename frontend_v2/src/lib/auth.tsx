import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';
import { api } from './api';
import {
  AUTH_EXPIRED_EVENT, clearStoredAuth, readStoredAuth, writeStoredAuth,
  type AuthUser,
} from './authStorage';

interface AuthContextValue {
  user: AuthUser | null;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredAuth()?.user ?? null);

  useEffect(() => {
    function handleExpired() { setUser(null); }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleExpired);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await api.login({ username, password });
    const stored = writeStoredAuth(response);
    setUser(stored.user);
    return stored.user;
  }, []);

  const logout = useCallback(() => {
    clearStoredAuth();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({ user, login, logout }), [user, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
