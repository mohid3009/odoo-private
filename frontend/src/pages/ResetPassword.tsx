import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { AuthShell } from "../components/Layout";
import ResourceForm from "../components/ResourceForm";

export default function ResetPassword() {
  const { uid, token } = useParams();

  return (
    <AuthShell title="Choose a new password">
      <ResourceForm
        submitLabel="Set new password"
        fields={[
          { name: "new_password", label: "New password", type: "password", required: true, autoComplete: "new-password", hint: "At least 9 characters with an uppercase letter, a lowercase letter and a special character." },
          { name: "confirm", label: "Confirm password", type: "password", required: true, autoComplete: "new-password", validate: (v, all) => v === all.new_password || "Passwords do not match." },
        ]}
        onSubmit={async (v) => { await api.get("/api/auth/csrf/"); return api.post("/api/auth/password-reset/confirm/", { uid, token, new_password: v.new_password }); }}
        successMessage="Password updated. You can log in now."
      />
      <p className="mt-4 text-sm"><Link className="text-indigo-700" to="/login">Go to log in</Link></p>
    </AuthShell>
  );
}
