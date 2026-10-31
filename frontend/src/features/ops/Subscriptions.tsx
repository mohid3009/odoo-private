import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import ResourceForm from "../../components/ResourceForm";
import StatusBadge from "../../components/StatusBadge";
import SubscriptionForm from "./SubscriptionForm";

const STATUSES = ["draft", "quotation", "confirmed", "active", "paused", "closed"];

export function SubscriptionsShell() {
  const tab = ({ isActive }: { isActive: boolean }) =>
    `rounded px-3 py-1 text-sm ${isActive ? "bg-sky-600 text-white" : "border bg-white text-slate-700"}`;
  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap gap-2" aria-label="Subscription sections">
        <NavLink to="/subscriptions" end className={tab}>Subscriptions</NavLink>
        <NavLink to="/subscriptions/templates" className={tab}>Quotation templates</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}

const columns: Column<any>[] = [
  { key: "number", header: "Number", render: (r) => <Link className="font-medium text-sky-700" to={`/subscriptions/${r.id}`}>{r.number}</Link> },
  { key: "customer_email", header: "Customer" },
  { key: "plan_name", header: "Plan" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "start_date", header: "Start" },
  { key: "expiry_date", header: "Expiry", render: (r) => r.expiry_date ?? "—" },
  { key: "lines_total", header: "Total (pre-tax)", render: (r) => <MoneyText value={r.lines_total} /> },
];

export function SubscriptionList() {
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [search, setSearch] = useState("");
  const plans = useQuery({ queryKey: ["options", "/api/plans/"], queryFn: () => api.get<Page<any>>("/api/plans/?page_size=200") });
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (plan) params.plan = plan;
  if (search) params.search = search;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Subscriptions</h1>
        <select aria-label="Filter by status" className="ml-auto rounded border px-2 py-1 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select aria-label="Filter by plan" className="rounded border px-2 py-1 text-sm" value={plan} onChange={(e) => setPlan(e.target.value)}>
          <option value="">All plans</option>
          {plans.data?.results.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input aria-label="Search" placeholder="Number or customer…" className="rounded border px-3 py-1 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
        <button className="rounded bg-sky-600 px-3 py-1 text-sm text-white" onClick={() => navigate("/subscriptions/new")}>New subscription</button>
      </div>
      <DataTable<any> queryKey="subscriptions" endpoint="/api/subscriptions/" columns={columns} params={params} empty="No subscriptions match."
        onRowClick={(r) => navigate(`/subscriptions/${r.id}`)} />
    </div>
  );
}

export function NewSubscription() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [mode, setMode] = useState<"template" | "blank">("template");
  const done = (sub: any) => { qc.invalidateQueries({ queryKey: ["subscriptions"] }); navigate(`/subscriptions/${sub.id}`); };
  const tab = (m: typeof mode, label: string) => (
    <button type="button" className={`rounded px-3 py-1 text-sm ${mode === m ? "bg-sky-600 text-white" : "border bg-white"}`} onClick={() => setMode(m)}>{label}</button>
  );

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">New subscription</h1>
      <div className="flex gap-2">{tab("template", "From a template")}{tab("blank", "From scratch")}</div>
      <div className="rounded border bg-white p-5">
        {mode === "template" ? (
          <ResourceForm
            submitLabel="Create draft from template"
            defaultValues={{ template: "", customer: "", start_date: "", expiry_date: "" }}
            fields={[
              { name: "template", label: "Template", type: "select", required: true, optionsFrom: { endpoint: "/api/quotation-templates/", label: (t) => `${t.name} — ${t.plan_name}` } },
              { name: "customer", label: "Customer", type: "select", required: true, optionsFrom: { endpoint: "/api/customers/", label: (c) => (c.name ? `${c.name} (${c.email})` : c.email) } },
              { name: "start_date", label: "Start date", type: "date", required: true },
              { name: "expiry_date", label: "Expiry date", type: "date" },
            ]}
            onSubmit={(v) => api.post("/api/subscriptions/from-template/", { ...v, template: Number(v.template), customer: Number(v.customer) }).then(done)}
          />
        ) : (
          <SubscriptionForm onSaved={done} onCancel={() => navigate("/subscriptions")} />
        )}
      </div>
    </div>
  );
}
