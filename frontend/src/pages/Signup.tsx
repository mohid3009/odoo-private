import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import ResourceForm from "../components/ResourceForm";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  return (
    <AuthShell title="Create your account">
      <ResourceForm
        submitLabel="Sign up"
        defaultValues={{ whatsapp_opt_in: false }}
        fields={[
          { name: "name", label: "Full name", autoComplete: "name" },
          { name: "email", label: "Email", type: "email", required: true, autoComplete: "email" },
          { name: "password", label: "Password", type: "password", required: true, autoComplete: "new-password", hint: "At least 9 characters with an uppercase letter, a lowercase letter and a special character." },
          { name: "whatsapp_number", label: "WhatsApp number (optional)", type: "tel", placeholder: "+919876543210", hint: "10-digit Indian numbers are assumed to be +91." },
          { name: "whatsapp_opt_in", label: "Send me invoice and reminder updates on WhatsApp", type: "checkbox" },
        ]}
        onSubmit={(v) => signup({ ...v, whatsapp_number: v.whatsapp_number ?? "" })}
        onSuccess={() => navigate("/", { replace: true })}
      />
      <p className="mt-4 text-sm">Already registered? <Link className="text-indigo-700" to="/login">Log in</Link></p>
    </AuthShell>
  );
}
