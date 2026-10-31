import { api } from "../api/client";
import type { User } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import type { Field } from "../components/ResourceForm";
import ResourceForm from "../components/ResourceForm";

const PROFILE_FIELDS: Field[] = [
  { name: "company_name", label: "Company" },
  { name: "phone", label: "Phone", type: "tel" },
  { name: "address", label: "Address", type: "textarea" },
  { name: "whatsapp_number", label: "WhatsApp number", type: "tel", placeholder: "+919876543210", hint: "10-digit Indian numbers are assumed to be +91." },
  { name: "whatsapp_opt_in", label: "Send me invoice and reminder updates on WhatsApp", type: "checkbox" },
  { name: "email_notifications", label: "Send me invoice and reminder emails", type: "checkbox" },
];

export default function Profile() {
  const { user, setUser } = useAuth();
  if (!user) return null;
  const hasProfile = !!user.profile;
  const fields: Field[] = [{ name: "name", label: "Name" }, ...(hasProfile ? PROFILE_FIELDS : [])];

  return (
    <div className="max-w-md">
      <h1 className="mb-1 text-xl font-semibold">Profile</h1>
      <p className="mb-4 text-sm text-slate-600">{user.email}</p>
      <div className="rounded border bg-white p-5">
        <ResourceForm
          submitLabel="Save"
          fields={fields}
          successMessage="Saved."
          defaultValues={{ name: user.name, ...(user.profile ?? {}) }}
          onSubmit={async (v) => {
            const { name, ...profile } = v;
            const updated = await api.patch<User>("/api/auth/me/", hasProfile ? { name, profile } : { name });
            setUser(updated);
          }}
        />
      </div>
    </div>
  );
}
