import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('socratiq_token');
    if (!token) {
      setLoading(false);
      return;
    }
    authApi.me()
      .then((u) => setUser(u))
      .catch(() => {
        localStorage.removeItem('socratiq_token');
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const data = await authApi.login(email, password);
    localStorage.setItem('socratiq_token', data.access_token);
    setUser({ user_id: data.user_id, email: data.email, display_name: data.display_name });
    return data;
  };

  const register = async (email, password, displayName) => {
    const data = await authApi.register(email, password, displayName);
    localStorage.setItem('socratiq_token', data.access_token);
    setUser({ user_id: data.user_id, email: data.email, display_name: data.display_name });
    return data;
  };

  const logout = () => {
    localStorage.removeItem('socratiq_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
