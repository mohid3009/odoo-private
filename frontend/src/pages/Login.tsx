import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import GoogleButton from "../components/GoogleButton";
import ResourceForm from "../components/ResourceForm";

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
      <GoogleButton label="Continue with Google" run={() => loginWithGoogle().then(done)} />
      <p className="my-4 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" /></p>
      <ResourceForm
        submitLabel="Log in"
        fields={[
          { name: "email", label: "Email", type: "email", required: true, autoComplete: "username" },
          { name: "password", label: "Password", type: "password", required: true, autoComplete: "current-password" },
        ]}
        onSubmit={(v) => login(v.email, v.password)}
        onSuccess={done}
      />
      <p className="mt-4 flex justify-between text-sm">
        <Link className="text-sky-700" to="/signup">Create an account</Link>
        <Link className="text-sky-700" to="/forgot-password">Forgot password?</Link>
      </p>
    </AuthShell>
  );
}
