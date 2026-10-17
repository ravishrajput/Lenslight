import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { http } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // null = checking, false = unauthenticated, object = user
  const [user, setUser] = useState(null);

  const checkAuth = useCallback(async () => {
    try {
      // validateStatus so 401 doesn't throw and get flagged as an unhandled rejection
      const res = await http.get("/auth/me", { validateStatus: (s) => s < 500 });
      if (res.status === 200) setUser(res.data);
      else setUser(false);
    } catch {
      setUser(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await http.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const register = async (payload) => {
    const { data } = await http.post("/auth/register", payload);
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await http.post("/auth/logout");
    } catch {}
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, login, register, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
