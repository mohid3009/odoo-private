import { Link } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "../components/Layout";
import ResourceForm from "../components/ResourceForm";

export default function ForgotPassword() {
  return (
    <AuthShell title="Reset your password">
      <ResourceForm
        submitLabel="Send reset link"
        fields={[{ name: "email", label: "Email", required: true, autoComplete: "email" }]}
        onSubmit={async (v) => { await api.get("/api/auth/csrf/"); return api.post("/api/auth/password-reset/request/", v); }}
        successMessage="If that email is registered, a reset link has been sent."
      />
      <p className="mt-4 text-sm"><Link className="text-indigo-700" to="/login">Back to log in</Link></p>
    </AuthShell>
  );
}
