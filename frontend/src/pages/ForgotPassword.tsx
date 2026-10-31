import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import ResourceForm from "../components/ResourceForm";

export default function ForgotPassword() {
  const { resetPassword } = useAuth();
  return (
    <AuthShell title="Reset your password">
      <ResourceForm
        submitLabel="Send reset link"
        fields={[{ name: "email", label: "Email", type: "email", required: true, autoComplete: "email" }]}
        onSubmit={(v) => resetPassword(v.email)}
        successMessage="If that email is registered, a reset link has been sent."
      />
      <p className="mt-4 text-sm"><Link className="text-sky-700" to="/login">Back to log in</Link></p>
    </AuthShell>
  );
}
