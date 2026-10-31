import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import ConfirmButton from "./ConfirmButton";
import DataTable, { Column } from "./DataTable";
import ResourceForm, { Field } from "./ResourceForm";

export interface CrudConfig<T> {
  title: string;
  noun: string; // "product"
  endpoint: string; // "/api/products/"
  queryKey: string;
  columns: Column<T>[];
  fields: Field[];
  defaults: Record<string, any>;
  toForm?: (row: T) => Record<string, any>; // API row -> form values
  toPayload?: (values: Record<string, any>) => Record<string, any>; // form values -> API body
  writeRoles?: Role[]; // who sees create/edit/delete; default admin only (the server enforces it either way)
}

// One config object = one catalog screen (rule 10). Staff see the list read-only; the server refuses their writes anyway.
export default function CrudPage<T extends { id: number }>({ config }: { config: CrudConfig<T> }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = !!user && (config.writeRoles ?? ["admin"]).includes(user.role);
  const [mode, setMode] = useState<{ row: T | null } | null>(null); // null = closed, row null = create
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  const refresh = () => {
    qc.invalidateQueries({ queryKey: [config.queryKey] });
    qc.invalidateQueries({ queryKey: ["options"] }); // dropdowns elsewhere
  };
  const close = () => setMode(null);

  const columns: Column<T>[] = canWrite
    ? [...config.columns, {
        key: "_actions", header: "", render: (row) => (
          <span className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
            <button className="text-sky-700" onClick={() => { setError(""); setMode({ row }); }}>Edit</button>
            <ConfirmButton danger label="Delete" onConfirm={async () => {
              setError("");
              try { await api.del(`${config.endpoint}${row.id}/`); refresh(); }
              catch (e) { setError(e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "Could not delete."); }
            }} />
          </span>
        ),
      }]
    : config.columns;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">{config.title}</h1>
        <input className="ml-auto rounded border px-3 py-1 text-sm" placeholder="Search…" aria-label="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        {canWrite && <button className="rounded bg-sky-600 px-3 py-1 text-sm text-white" onClick={() => { setError(""); setMode({ row: null }); }}>New {config.noun}</button>}
      </div>
      {!canWrite && <p className="text-sm text-slate-500">Read-only for your role.</p>}
      {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {canWrite && mode && (
        <div className="max-w-2xl rounded border bg-white p-5">
          <h2 className="mb-3 font-semibold">{mode.row ? `Edit ${config.noun}` : `New ${config.noun}`}</h2>
          <ResourceForm
            key={mode.row?.id ?? "new"}
            fields={config.fields}
            submitLabel={mode.row ? "Save changes" : `Create ${config.noun}`}
            defaultValues={mode.row ? (config.toForm ? config.toForm(mode.row) : (mode.row as any)) : config.defaults}
            onSubmit={(v) => {
              const body = config.toPayload ? config.toPayload(v) : v;
              return mode.row ? api.patch(`${config.endpoint}${mode.row.id}/`, body) : api.post(config.endpoint, body);
            }}
            onSuccess={() => { refresh(); close(); }}
            onCancel={close}
          />
        </div>
      )}

      <DataTable<T> queryKey={config.queryKey} endpoint={config.endpoint} columns={columns} params={search ? { search } : undefined}
        empty={`No ${config.noun}s yet.`} onRowClick={canWrite ? (row) => { setError(""); setMode({ row }); } : undefined} />
    </div>
  );
}
