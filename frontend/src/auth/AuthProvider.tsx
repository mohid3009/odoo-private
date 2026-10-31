import { createContext, ReactNode, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import type { User } from "../api/types";

interface Auth {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (body: Record<string, unknown>) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}

const Ctx = createContext<Auth>(null as unknown as Auth);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    staleTime: Infinity,
    queryFn: async () => {
      await api.get("/api/auth/csrf/"); // makes sure the csrftoken cookie exists before any POST
      try {
        return await api.get<User>("/api/auth/me/");
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null; // logged out
        throw e;
      }
    },
  });

  const setUser = (u: User | null) => qc.setQueryData(["me"], u);
  // drop cached data of the previous identity, but keep the observed ["me"] query alive
  const dropCache = () => qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });

  const login = async (email: string, password: string) => {
    await api.get("/api/auth/csrf/");
    const u = await api.post<User>("/api/auth/login/", { email, password });
    dropCache();
    setUser(u);
    return u;
  };

  const signup = async (body: Record<string, unknown>) => {
    await api.get("/api/auth/csrf/");
    await api.post("/api/auth/signup/", body);
    return login(String(body.email), String(body.password));
  };

  const logout = async () => {
    await api.post("/api/auth/logout/");
    dropCache();
    setUser(null);
  };

  return <Ctx.Provider value={{ user: data ?? null, loading: isLoading, login, signup, logout, setUser }}>{children}</Ctx.Provider>;
}
