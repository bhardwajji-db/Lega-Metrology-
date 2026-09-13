import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { type AuthUser } from '../types';
import { api, tokenStore } from '../services/api';

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  register: (username: string, email: string, password: string, fullName?: string) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(tokenStore.get());
  const [loading, setLoading] = useState<boolean>(true);

  // Restore session on load: if a token exists, validate it via /auth/me
  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      const saved = tokenStore.get();
      if (!saved) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.getMe();
        if (!cancelled) {
          setUser(me);
          setToken(saved);
        }
      } catch {
        tokenStore.clear();
        if (!cancelled) setToken(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    restore();
    return () => { cancelled = true; };
  }, []);

  const login = async (username: string, password: string): Promise<AuthUser> => {
    const res = await api.login(username, password);
    tokenStore.set(res.token);
    setToken(res.token);
    setUser(res.user);
    return res.user;
  };

  const register = async (username: string, email: string, password: string, fullName?: string): Promise<AuthUser> => {
    const res = await api.register({ username, email, password, full_name: fullName });
    tokenStore.set(res.token);
    setToken(res.token);
    setUser(res.user);
    return res.user;
  };

  const logout = () => {
    tokenStore.clear();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}