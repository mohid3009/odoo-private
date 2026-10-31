import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

// Customer portal, read-only (FR-PORT-01). Another customer's id is a 404 from the API, shown as "not found".
const invoiceColumns: Column<any>[] = [
  { key: "number", header: "Invoice", render: (r) => <Link className="font-medium text-indigo-700" to={`/invoices/${r.id}/print`}>{r.number}</Link> },
  { key: "period", header: "Period", render: (r) => `${r.period_start} → ${r.period_end}` },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "due_date", header: "Due", render: (r) => (r.is_overdue ? <span className="font-medium text-red-700">{r.due_date} · overdue</span> : r.due_date) },
  { key: "total", header: "Total", render: (r) => <MoneyText value={r.total} /> },
  { key: "amount_due", header: "Balance", render: (r) => <MoneyText value={r.amount_due} /> },
];

export default function MySubscriptionDetail() {
  const { id } = useParams();
  const { data: s, isLoading, isError } = useQuery({ queryKey: ["my-subscriptions", "detail", id], queryFn: () => api.get<any>(`/api/subscriptions/${id}/`) });

  if (isLoading) return <p className="py-6 text-slate-500">Loading…</p>;
  if (isError || !s) return <p className="py-6 text-red-700">Subscription not found. <Link className="text-indigo-700" to="/my-subscriptions">Back to my subscriptions</Link></p>;

  const facts: [string, string | null][] = [
    ["Plan", s.plan_name], ["Start", s.start_date], ["Expiry", s.expiry_date], ["Next invoice", s.next_invoice_date],
    ["Payment terms", s.payment_term_name], ["Discount", s.discount_name || null],
  ];
  return (
    <div className="space-y-5">
      <Link className="text-sm text-indigo-700" to="/my-subscriptions">← My subscriptions</Link>
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">{s.number}</h1>
        <StatusBadge status={s.status} />
      </div>
      <dl className="grid grid-cols-2 gap-3 rounded border bg-white p-4 text-sm md:grid-cols-3">
        {facts.map(([k, v]) => <div key={k}><dt className="text-xs uppercase text-slate-500">{k}</dt><dd>{v ?? "—"}</dd></div>)}
      </dl>

      <section>
        <h2 className="mb-2 font-semibold">Lines</h2>
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr>{["Product", "Qty", "Unit price", "Amount"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {s.lines.map((l: any) => (
                <tr key={l.id} className="border-t">
                  <td className="px-3 py-2">{l.description || l.product_name}{l.variant_label ? <span className="text-slate-500"> · {l.variant_label}</span> : null}</td>
                  <td className="px-3 py-2">{l.quantity}</td>
                  <td className="px-3 py-2"><MoneyText value={l.unit_price} /></td>
                  <td className="px-3 py-2"><MoneyText value={l.amount} /></td>
                </tr>
              ))}
              <tr className="border-t font-medium"><td className="px-3 py-2" colSpan={3}>Total per period (before tax)</td><td className="px-3 py-2"><MoneyText value={s.lines_total} /></td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Invoices</h2>
        <DataTable queryKey="my-invoices" endpoint="/api/invoices/" params={{ subscription: String(s.id) }} columns={invoiceColumns} empty="No invoices for this subscription yet." />
      </section>
    </div>
  );
}
