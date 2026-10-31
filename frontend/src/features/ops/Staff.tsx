import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { User } from "../../api/types";
import DataTable, { Column } from "../../components/DataTable";
import ResourceForm from "../../components/ResourceForm";
import StatusBadge from "../../components/StatusBadge";

const columns: Column<User & { created_at: string }>[] = [
  { key: "email", header: "Email" },
  { key: "name", header: "Name" },
  { key: "role", header: "Role", render: (r) => <StatusBadge status={r.role} /> },
  { key: "created_at", header: "Created", render: (r) => new Date(r.created_at).toLocaleDateString() },
];

export default function Staff() {
  const qc = useQueryClient();
  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-3 text-xl font-semibold">Staff accounts</h1>
        <DataTable queryKey="staff" endpoint="/api/staff/" columns={columns} />
      </section>
      <section className="max-w-md">
        <h2 className="mb-3 text-lg font-semibold">Add a staff member</h2>
        <div className="rounded border bg-white p-5">
          <ResourceForm
            submitLabel="Create staff account"
            resetOnSuccess
            defaultValues={{ role: "staff" }}
            successMessage="Account created. They can now sign in with Google, or with email and password using this address."
            fields={[
              { name: "name", label: "Name" },
              { name: "email", label: "Email", type: "email", required: true },
              { name: "password", label: "Local password (optional)", type: "password", autoComplete: "new-password", hint: "Only used when local login is enabled (dev). Leave empty in production: staff sign in through Firebase with this email." },
              { name: "role", label: "Role", type: "select", options: [{ value: "staff", label: "Staff" }, { value: "admin", label: "Admin" }] },
            ]}
            onSubmit={(v) => api.post("/api/staff/", v)}
            onSuccess={() => qc.invalidateQueries({ queryKey: ["staff"] })}
          />
        </div>
      </section>
    </div>
  );
}
