import { createContext, ReactNode, useContext } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createUserWithEmailAndPassword, sendEmailVerification, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPopup, signOut,
  type User as FbUser,
} from "firebase/auth";
import { api, ApiError } from "../api/client";
import type { User } from "../api/types";
import { fbAuth, google } from "./firebase";

type Extra = Record<string, unknown>;

interface Auth {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  loginWithGoogle: (extra?: Extra) => Promise<User>;
  demoLogin: (role: "user" | "staff" | "admin") => Promise<User>;
  signup: (body: Extra) => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}

const Ctx = createContext<Auth>(null as unknown as Auth);
export const useAuth = () => useContext(Ctx);

// Sign-up details (account type, registration code, WhatsApp) wait here while the person verifies their email,
// then ride along on their first sign-in. The server ignores them for accounts that already exist.
const PENDING = "bl_signup_extra";
const readPending = (email: string): Extra => {
  try {
    const p = JSON.parse(localStorage.getItem(PENDING) || "null");
    return p && p.email === String(email).toLowerCase() ? p.extra : {};
  } catch {
    return {};
  }
};
const clearPending = () => { try { localStorage.removeItem(PENDING); } catch { /* storage blocked: nothing to clean */ } };

const MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "Invalid email or password.",
  "auth/wrong-password": "Invalid email or password.",
  "auth/user-not-found": "Invalid email or password.",
  "auth/email-already-in-use": "An account with this email already exists. Log in instead.",
  "auth/weak-password": "Password is too weak.",
  "auth/too-many-requests": "Too many attempts. Try again in a few minutes.",
  "auth/popup-closed-by-user": "Sign-in was cancelled.",
  "auth/popup-blocked": "Your browser blocked the sign-in window. Allow pop-ups and retry.",
  "auth/network-request-failed": "Network error. Please try again.",
  "auth/api-key-not-valid.-please-pass-a-valid-api-key.": "Sign-in isn't configured: set the VITE_FIREBASE_* values (see frontend/.env.example) and rebuild.",
  "auth/invalid-api-key": "Sign-in isn't configured: set the VITE_FIREBASE_* values (see frontend/.env.example) and rebuild.",
  "auth/unauthorized-domain": "This address isn't authorised for sign-in. Add it under Firebase → Authentication → Settings → Authorized domains.",
};
// ResourceForm shows ApiError bodies, so Firebase failures are re-thrown in that shape.
const fail = (e: unknown): never => {
  if (e instanceof ApiError) throw e;
  const code = (e as { code?: string })?.code ?? "";
  throw new ApiError(400, { detail: MESSAGES[code] ?? (e as Error)?.message ?? "Sign-in failed." });
};

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

  // Firebase proves who they are; the server turns the ID token into the usual Django session cookie.
  const exchange = async (fb: FbUser, extra: Extra = {}) => {
    try {
      const id_token = await fb.getIdToken(true);
      await api.get("/api/auth/csrf/");
      const u = await api.post<User>("/api/auth/firebase/", { ...readPending(fb.email ?? ""), ...extra, id_token });
      dropCache();
      setUser(u);
      return u;
    } catch (e) {
      await signOut(fbAuth).catch(() => undefined);
      return fail(e);
    } finally {
      clearPending();
    }
  };

  const loginWithGoogle = async (extra?: Extra) => {
    let fb: FbUser;
    try {
      fb = (await signInWithPopup(fbAuth, google)).user;
    } catch (e) {
      return fail(e);
    }
    return exchange(fb, extra);
  };

  const login = async (email: string, password: string) => {
    let fb: FbUser;
    try {
      fb = (await signInWithEmailAndPassword(fbAuth, email.trim(), password)).user;
    } catch (e) {
      return fail(e);
    }
    if (!fb.emailVerified) {
      await sendEmailVerification(fb).catch(() => undefined);
      await signOut(fbAuth);
      return fail(new ApiError(403, { detail: "Verify your email first. We just sent a new link; open it, then log in." }));
    }
    return exchange(fb);
  };

  // Quick sign-in for the demo accounts: a separate server endpoint (404 unless DEMO_LOGIN_ENABLED), no Firebase involved.
  const demoLogin = async (role: "user" | "staff" | "admin") => {
    await api.get("/api/auth/csrf/");
    const u = await api.post<User>("/api/auth/demo/", { role });
    dropCache();
    setUser(u);
    return u;
  };

  // Creates the Firebase account and sends the verification link. The person is not signed in until they verify and log in.
  const signup = async (body: Extra) => {
    const { email, password, ...extra } = body;
    try {
      const fb = (await createUserWithEmailAndPassword(fbAuth, String(email).trim(), String(password))).user;
      await sendEmailVerification(fb);
      await signOut(fbAuth);
      localStorage.setItem(PENDING, JSON.stringify({ email: String(email).trim().toLowerCase(), extra }));
    } catch (e) {
      fail(e);
    }
  };

  const resetPassword = async (email: string) => {
    try {
      await sendPasswordResetEmail(fbAuth, email.trim());
    } catch (e) {
      if ((e as { code?: string })?.code !== "auth/user-not-found") fail(e); // never reveal whether an account exists
    }
  };

  const logout = async () => {
    await api.post("/api/auth/logout/");
    await signOut(fbAuth).catch(() => undefined);
    dropCache();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user: data ?? null, loading: isLoading, login, loginWithGoogle, demoLogin, signup, resetPassword, logout, setUser }}>
      {children}
    </Ctx.Provider>
  );
}
