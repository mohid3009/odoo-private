import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import GoogleButton from "../components/GoogleButton";
import ResourceForm from "../components/ResourceForm";

// demo build: one-click sign-in for the seeded demo accounts. Set VITE_SHOW_DEMO=false on the host to hide it.
const SHOW_DEMO = import.meta.env.VITE_SHOW_DEMO !== "false";
const DEMOS = [
  { role: "user", label: "Customer", email: "user1@gmail.com" },
  { role: "staff", label: "Staff", email: "staff1@gmail.com" },
  { role: "admin", label: "Admin", email: "admin1@gmail.com" },
] as const;

function QuickSignIn({ onDone }: { onDone: () => void }) {
  const { demoLogin } = useAuth();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const go = async (role: (typeof DEMOS)[number]["role"]) => {
    setBusy(role);
    setErr("");
    try {
      await demoLogin(role);
      onDone();
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 404 ? "Demo sign-in is switched off on this server." : "Demo sign-in failed. Please try again.");
    } finally {
      setBusy("");
    }
  };
  return (
    <div className="mt-6 rounded-xl border border-dashed p-3">
      <p className="mb-2 text-xs font-medium text-slate-600">Quick demo sign-in</p>
      <div className="grid grid-cols-3 gap-2">
        {DEMOS.map((d) => (
          <button key={d.role} type="button" disabled={!!busy} onClick={() => go(d.role)} title={d.email}
            className="rounded-lg border bg-white px-2 py-2 text-xs font-medium text-slate-800 transition hover:shadow-md disabled:opacity-60">
            {busy === d.role ? "…" : d.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">user1@ · staff1@ · admin1@gmail.com, sample data included. Real sign-in above is unaffected.</p>
      {err && <p role="alert" className="mt-2 text-xs text-red-700">{err}</p>}
    </div>
  );
}

export default function Login() {
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const done = () => navigate(from, { replace: true });

  return (
    <AuthShell title="Log in">
      <p className="mb-4 text-sm">
        <Link className="text-sky-700" to="/welcome">← Home</Link>
      </p>
      <ResourceForm
        submitLabel="Log in"
        fields={[
          { name: "email", label: "Email", type: "email", required: true, autoComplete: "username" },
          { name: "password", label: "Password", type: "password", required: true, autoComplete: "current-password" },
        ]}
        onSubmit={(v) => login(v.email, v.password)}
        onSuccess={done}
      />
      <p className="my-4 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" /></p>
      <GoogleButton label="Continue with Google" run={() => loginWithGoogle().then(done)} />
      {SHOW_DEMO && <QuickSignIn onDone={done} />}
      <p className="mt-4 flex justify-between text-sm">
        <Link className="text-sky-700" to="/signup">Create an account</Link>
        <Link className="text-sky-700" to="/forgot-password">Forgot password?</Link>
      </p>
    </AuthShell>
  );
}
