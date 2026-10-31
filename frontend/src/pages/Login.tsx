import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import ResourceForm from "../components/ResourceForm";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";

  return (
    <AuthShell title="Log in">
      <ResourceForm
        submitLabel="Log in"
        fields={[
          { name: "email", label: "Email", required: true, autoComplete: "username" },
          { name: "password", label: "Password", type: "password", required: true, autoComplete: "current-password" },
        ]}
        onSubmit={(v) => login(v.email, v.password)}
        onSuccess={() => navigate(from, { replace: true })}
      />
      <p className="mt-4 flex justify-between text-sm">
        <Link className="text-indigo-700" to="/signup">Create an account</Link>
        <Link className="text-indigo-700" to="/forgot-password">Forgot password?</Link>
      </p>
    </AuthShell>
  );
}
