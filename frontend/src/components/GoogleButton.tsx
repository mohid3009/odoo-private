import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

// Runs a Google sign-in and shows the failure inline (the form components only cover their own submit).
export default function GoogleButton({ label, run }: { label: string; run: () => Promise<unknown> }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [slow, setSlow] = useState(false);
  // a sleeping host (free tier) can take up to a minute to answer the first request
  useEffect(() => {
    if (!busy) return setSlow(false);
    const t = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(t);
  }, [busy]);
  const click = async () => {
    setBusy(true);
    setErr("");
    try {
      await run();
    } catch (e) {
      const d = e instanceof ApiError && e.body && typeof e.body === "object" ? (e.body as Record<string, unknown>) : null;
      const http = e instanceof ApiError ? ` (server answered ${e.status})` : "";
      setErr(String(d?.detail ?? Object.values(d ?? {}).flat()[0] ?? `Sign-in failed${http}. Please try again.`));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div>
      <button type="button" onClick={click} disabled={busy} className="flex w-full items-center justify-center gap-3 rounded-xl border bg-white px-4 py-2.5 text-sm font-medium text-slate-800 shadow-sm transition hover:shadow-md disabled:opacity-60">
        <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
          <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
          <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.5-4.1 7-10.2 7-17.6z" />
          <path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6l7.9-6.1z" />
          <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
        </svg>
        {busy ? "Opening Google…" : label}
      </button>
      {slow && !err && <p role="status" className="mt-2 text-sm text-slate-600">Still working. The server may be waking up, which can take up to a minute. Please keep this page open.</p>}
      {err && <p role="alert" className="mt-2 text-sm text-red-700">{err}</p>}
    </div>
  );
}
