import { useState } from "react";
import { Link } from "react-router-dom";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

const columns: Column<any>[] = [
  { key: "payment_date", header: "Date" },
  { key: "invoice_number", header: "Invoice", render: (r) => <Link className="text-indigo-700" to={`/invoices/${r.invoice}`}>{r.invoice_number ?? `#${r.invoice}`}</Link> },
  { key: "customer_email", header: "Customer" },
  { key: "attempt_number", header: "Attempt" },
  { key: "method", header: "Method", render: (r) => r.method.replace("_", " ") },
  { key: "amount", header: "Amount", render: (r) => <span className={r.status === "completed" ? "" : "line-through"}><MoneyText value={r.amount} /></span> },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  {
    key: "details", header: "Details",
    render: (r) => (
      <span className="text-xs">
        {r.status === "failed" && <span className="text-red-700">{r.failure_reason}</span>}
        {r.retry_of && <span className="block text-slate-500">retry of #{r.retry_of}</span>}
        {r.status === "reversed" && <span className="block">reversed: {r.reversal_reason}</span>}
        {r.note && <span className="block text-slate-500">{r.note}</span>}
      </span>
    ),
  },
];

// Every payment attempt across invoices (staff/admin). The per-invoice actions (retry, reverse) live on the invoice screen.
export default function Payments() {
  const [status, setStatus] = useState("");
  const [method, setMethod] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [search, setSearch] = useState("");
  const [attention, setAttention] = useState(false);
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (method) params.method = method;
  if (from) params.payment_date_after = from;
  if (to) params.payment_date_before = to;
  if (search) params.search = search;
  if (attention) params.needs_attention = "true";

  const sel = "rounded border px-2 py-1 text-sm";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold">Payments</h1>
        <select aria-label="Filter by status" className={`${sel} ml-auto`} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["completed", "failed", "reversed"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select aria-label="Filter by method" className={sel} value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="">All methods</option>
          {["cash", "bank_transfer", "upi", "card", "cheque", "other"].map((m) => <option key={m} value={m}>{m.replace("_", " ")}</option>)}
        </select>
        <label className="text-sm">From <input aria-label="From date" type="date" className={sel} value={from} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="text-sm">To <input aria-label="To date" type="date" className={sel} value={to} onChange={(e) => setTo(e.target.value)} /></label>
        <input aria-label="Search" placeholder="Invoice, customer or note…" className={sel} value={search} onChange={(e) => setSearch(e.target.value)} />
        <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={attention} onChange={(e) => setAttention(e.target.checked)} /> Needs attention</label>
      </div>
      <DataTable<any> queryKey="payments" endpoint="/api/payments/" columns={columns} params={params} empty="No payments match." />
    </div>
  );
}
