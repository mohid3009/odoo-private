import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// Public web config (see frontend/.env.example). Firebase only identifies the person; roles and data access stay in Django.
const app = initializeApp({
  // A missing key must not crash the whole app at import time (getAuth throws auth/invalid-api-key and the page goes blank).
  // With a placeholder the pages still render and sign-in reports "not configured" (see AuthProvider MESSAGES).
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "not-configured",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});

export const fbAuth = getAuth(app);
export const google = new GoogleAuthProvider();
