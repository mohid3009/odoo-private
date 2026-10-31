import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

const CHIPS: { key: string; label: string; params: Record<string, string> }[] = [
  { key: "all", label: "All", params: {} },
  { key: "draft", label: "Draft", params: { status: "draft" } },
  { key: "confirmed", label: "Confirmed", params: { status: "confirmed" } },
  { key: "paid", label: "Paid", params: { status: "paid" } },
  { key: "overdue", label: "Overdue", params: { overdue: "true" } },
  { key: "cancelled", label: "Cancelled", params: { status: "cancelled" } },
];

const columns: Column<any>[] = [
  { key: "number", header: "Invoice", render: (r) => <Link className="font-medium text-indigo-700" to={`/invoices/${r.id}`}>{r.number ?? `Draft #${r.id}`}</Link> },
  { key: "customer_email", header: "Customer" },
  { key: "subscription_number", header: "Subscription" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "period", header: "Period", render: (r) => `${r.period_start} → ${r.period_end}` },
  {
    key: "due_date", header: "Due",
    render: (r) => r.is_overdue
      ? <span className="font-medium text-red-700">{r.due_date} · {r.days_overdue} day{r.days_overdue === 1 ? "" : "s"} overdue</span>
      : r.due_date,
  },
  { key: "total", header: "Total", render: (r) => <MoneyText value={r.total} /> },
  { key: "amount_due", header: "Balance", render: (r) => <MoneyText value={r.amount_due} /> },
  { key: "odoo_sync_status", header: "Odoo", render: (r) => <StatusBadge status={r.odoo_sync_status} /> },
];

export function InvoiceList() {
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const [chip, setChip] = useState(CHIPS.some((c) => c.key === sp.get("status")) ? sp.get("status")! : "all"); // /invoices?status=draft
  const [search, setSearch] = useState("");
  const params = { ...CHIPS.find((c) => c.key === chip)!.params, ...(search ? { search } : {}) };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Invoices</h1>
        <input aria-label="Search" placeholder="Number, subscription or customer…" className="ml-auto rounded border px-3 py-1 text-sm" value={search} onChange={(e) => setSearch(e.target.value)} />
        <button className="rounded border px-3 py-1 text-sm" onClick={() => navigate("/billing")}>Run billing</button>
      </div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Invoice filters">
        {CHIPS.map((c) => (
          <button key={c.key} type="button" aria-pressed={chip === c.key} onClick={() => setChip(c.key)}
            className={`rounded-full px-3 py-1 text-sm ${chip === c.key ? "bg-indigo-600 text-white" : "border bg-white text-slate-700"}`}>
            {c.label}
          </button>
        ))}
      </div>
      <DataTable<any> queryKey="invoices" endpoint="/api/invoices/" columns={columns} params={params} empty="No invoices match."
        onRowClick={(r) => navigate(`/invoices/${r.id}`)} />
    </div>
  );
}
