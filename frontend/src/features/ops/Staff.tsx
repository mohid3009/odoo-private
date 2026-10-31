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
            successMessage="Account created. Share the temporary password securely."
            fields={[
              { name: "name", label: "Name" },
              { name: "email", label: "Email", type: "email", required: true },
              { name: "password", label: "Temporary password", type: "password", required: true, autoComplete: "new-password", hint: "Same rules as everyone: 9+ characters, upper, lower and special." },
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
