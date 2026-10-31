import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import ConfirmButton from "../../components/ConfirmButton";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd>{children}</dd></div>;
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const { data: inv, isLoading, isError } = useQuery({ queryKey: ["invoices", "detail", id], queryFn: () => api.get<any>(`/api/invoices/${id}/`) });

  if (isLoading) return <p className="py-6 text-slate-500">Loading…</p>;
  if (isError || !inv) return <p className="py-6 text-red-700">Invoice not found. <Link className="text-indigo-700" to="/invoices">Back to the list</Link></p>;

  const act = async (action: "confirm" | "cancel" | "send", message = "") => {
    setError(""); setNote("");
    try {
      const fresh = await api.post<any>(`/api/invoices/${id}/${action}/`);
      qc.setQueryData(["invoices", "detail", id], fresh);
      qc.invalidateQueries({ queryKey: ["invoices", "list"] });
      if (message) setNote(message);
    } catch (e) {
      setError(e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "Could not complete that action.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link className="text-sm text-indigo-700" to="/invoices">← Invoices</Link>
        <h1 className="text-xl font-semibold">{inv.number ?? `Draft invoice #${inv.id}`}</h1>
        <StatusBadge status={inv.status} />
        {inv.is_overdue && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">{inv.days_overdue} days overdue</span>}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {inv.actions.includes("confirm") && <button className="rounded bg-indigo-600 px-3 py-1 text-sm text-white" onClick={() => act("confirm", "Confirmed. The customer has been notified.")}>Confirm</button>}
          {inv.actions.includes("send") && <button className="rounded border px-3 py-1 text-sm" onClick={() => act("send", "Invoice sent to the customer.")}>Send</button>}
          <Link className="rounded border px-3 py-1 text-sm" to={`/invoices/${id}/print`}>Print</Link>
          {inv.actions.includes("cancel") && <ConfirmButton danger label="Cancel invoice" confirmText="Cancel this invoice?" onConfirm={() => act("cancel")} />}
        </div>
      </div>
      {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {note && <p role="status" className="rounded bg-green-50 px-3 py-2 text-sm text-green-800">{note}</p>}

      <dl className="grid gap-4 rounded border bg-white p-4 sm:grid-cols-3">
        <Field label="Customer">{inv.customer_email}</Field>
        <Field label="Subscription"><Link className="text-indigo-700" to={`/subscriptions/${inv.subscription}`}>{inv.subscription_number}</Link></Field>
        <Field label="Service period">{inv.period_start} → {inv.period_end}</Field>
        <Field label="Invoice date">{inv.invoice_date}</Field>
        <Field label="Due date">{inv.due_date}</Field>
        <Field label="Sent">{inv.sent_at ? new Date(inv.sent_at).toLocaleString() : "—"}</Field>
        <Field label="Odoo">
          <StatusBadge status={inv.odoo_sync_status} />{inv.odoo_move_id ? <span className="ml-2 text-xs text-slate-500">move #{inv.odoo_move_id}</span> : null}
          {inv.odoo_error && <p className="mt-1 text-xs text-amber-700">{inv.odoo_error}</p>}
        </Field>
      </dl>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>{["Description", "Qty", "Unit price", "Tax", "Amount", "Total"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {inv.lines.map((l: any) => (
              <tr key={l.id} className={`border-t ${l.kind === "discount" ? "bg-green-50 text-green-900" : ""}`}>
                <td className="px-3 py-2">{l.description}</td>
                <td className="px-3 py-2">{l.quantity}</td>
                <td className="px-3 py-2"><MoneyText value={l.unit_price} /></td>
                <td className="px-3 py-2">{l.tax_rate}%</td>
                <td className="px-3 py-2"><MoneyText value={l.line_subtotal} /></td>
                <td className="px-3 py-2"><MoneyText value={l.line_total} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl className="ml-auto grid max-w-sm grid-cols-2 gap-x-4 gap-y-1 rounded border bg-white p-4 text-sm">
        <dt>Subtotal</dt><dd className="text-right"><MoneyText value={inv.subtotal} /></dd>
        <dt>Discounts</dt><dd className="text-right"><MoneyText value={`-${inv.discount_total}`} /></dd>
        <dt>Tax</dt><dd className="text-right"><MoneyText value={inv.tax_total} /></dd>
        <dt className="font-semibold">Total</dt><dd className="text-right font-semibold"><MoneyText value={inv.total} /></dd>
        <dt>Paid</dt><dd className="text-right"><MoneyText value={inv.amount_paid} /></dd>
        <dt className="font-semibold">Balance due</dt><dd className="text-right font-semibold"><MoneyText value={inv.amount_due} /></dd>
      </dl>
    </div>
  );
}
