import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthProvider";
import ConfirmButton from "../../components/ConfirmButton";
import Modal from "../../components/Modal";
import MoneyText from "../../components/MoneyText";
import ResourceForm from "../../components/ResourceForm";
import StatusBadge from "../../components/StatusBadge";
import NotificationTimeline from "./NotificationTimeline";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd>{children}</dd></div>;
}

const METHODS = ["cash", "bank_transfer", "upi", "card", "cheque", "other"].map((v) => ({ value: v, label: v.replace("_", " ") }));
type Dialog = { kind: "pay" } | { kind: "retry"; p: any } | { kind: "reverse"; p: any } | { kind: "reset" } | null;

// Payment attempts: record, retry a failed one, reverse a completed one (admin), reset the attempt limit (admin).
function PaymentsSection({ inv, onChanged }: { inv: any; onChanged: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [dialog, setDialog] = useState<Dialog>(null);
  const canPay = inv.actions.includes("pay");
  const done = () => { setDialog(null); onChanged(); };
  const today = new Date().toLocaleDateString("en-CA");
  const retriable = (p: any) => p.status === "failed" && !p.retried_by && canPay;

  const attemptForm = (retryOf?: any) => (
    <ResourceForm
      submitLabel={retryOf ? "Retry payment" : "Record payment"}
      defaultValues={{ amount: retryOf ? retryOf.amount : inv.amount_due, method: retryOf ? retryOf.method : "bank_transfer", payment_date: today, status: "completed", failure_reason: "", note: "" }}
      fields={[
        { name: "amount", label: "Amount", type: "money", required: true, hint: `Balance due: ₹${inv.amount_due}. More than the balance is rejected.` },
        { name: "method", label: "Method", type: "select", options: METHODS },
        { name: "payment_date", label: "Payment date", type: "date" },
        { name: "status", label: "Result of this attempt", type: "select", options: [{ value: "completed", label: "Completed — money received" }, { value: "failed", label: "Failed — no money received" }] },
        { name: "failure_reason", label: "Why it failed", hint: "Required when the result is Failed (e.g. card declined, cheque bounced)." },
        { name: "note", label: "Note", type: "textarea" },
      ]}
      onSubmit={(v) => api.post(retryOf ? `/api/payments/${retryOf.id}/retry/` : `/api/invoices/${inv.id}/payments/`, { ...v, payment_date: v.payment_date ?? undefined })}
      onSuccess={done}
      onCancel={() => setDialog(null)}
    />
  );
  const reasonForm = (label: string, url: string, submit: string) => (
    <ResourceForm submitLabel={submit} defaultValues={{ reason: "" }} fields={[{ name: "reason", label, type: "textarea", required: true }]}
      onSubmit={(v) => api.post(url, { reason: v.reason })} onSuccess={done} onCancel={() => setDialog(null)} />
  );

  return (
    <section className="space-y-3" aria-label="Payments">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Payments</h2>
        <span className="text-sm text-slate-600">Failed attempts: <strong>{inv.failed_attempts}</strong> of {inv.max_payment_attempts}</span>
        {canPay && <button className="ml-auto rounded bg-sky-600 px-3 py-1 text-sm text-white" onClick={() => setDialog({ kind: "pay" })}>Record payment</button>}
      </div>

      {inv.payment_needs_attention && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          <strong>Payment needs attention.</strong>
          <span>{inv.failed_attempts} attempts failed; no more can be recorded until an admin reviews this invoice.</span>
          {inv.actions.includes("reset_attempts") && <button className="ml-auto rounded border border-red-400 bg-white px-3 py-1" onClick={() => setDialog({ kind: "reset" })}>Reset attempts</button>}
        </div>
      )}

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>{["#", "Date", "Method", "Amount", "Status", "Details", ""].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {inv.payments.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-slate-500">No payment attempts yet.</td></tr>}
            {inv.payments.map((p: any) => (
              <tr key={p.id} className={`border-t ${p.status !== "completed" ? "text-slate-600" : ""}`}>
                <td className="px-3 py-2">{p.attempt_number}</td>
                <td className="px-3 py-2">{p.payment_date}</td>
                <td className="px-3 py-2">{p.method.replace("_", " ")}</td>
                <td className={`px-3 py-2 ${p.status === "completed" ? "" : "line-through"}`}><MoneyText value={p.amount} /></td>
                <td className="px-3 py-2"><StatusBadge status={p.status} /></td>
                <td className="px-3 py-2 text-xs">
                  {p.status === "failed" && <span className="text-red-700">{p.failure_reason}</span>}
                  {p.retry_of && <span className="block text-slate-500">retry of #{p.retry_of}</span>}
                  {p.retried_by && <span className="block text-slate-500">retried as #{p.retried_by}</span>}
                  {p.status === "reversed" && <span className="block">reversed by {p.reversed_by_email}: {p.reversal_reason}</span>}
                  {p.note && <span className="block text-slate-500">{p.note}</span>}
                  <span className="block text-slate-400">by {p.recorded_by_email ?? "—"}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  {retriable(p) && <button className="mr-2 text-sky-700" onClick={() => setDialog({ kind: "retry", p })}>Retry</button>}
                  {isAdmin && p.status === "completed" && <button className="text-red-700" onClick={() => setDialog({ kind: "reverse", p })}>Reverse</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {dialog?.kind === "pay" && <Modal title="Record a payment" onClose={() => setDialog(null)}>{attemptForm()}</Modal>}
      {dialog?.kind === "retry" && <Modal title={`Retry attempt #${dialog.p.attempt_number}`} onClose={() => setDialog(null)}>{attemptForm(dialog.p)}</Modal>}
      {dialog?.kind === "reverse" && (
        <Modal title={`Reverse payment of ₹${dialog.p.amount}`} onClose={() => setDialog(null)}>
          <p className="mb-3 text-sm text-slate-600">The payment stays on file as reversed and the balance is restored. A paid invoice goes back to confirmed.</p>
          {reasonForm("Reason for the reversal", `/api/payments/${dialog.p.id}/reverse/`, "Reverse payment")}
        </Modal>
      )}
      {dialog?.kind === "reset" && (
        <Modal title="Reset payment attempts" onClose={() => setDialog(null)}>
          <p className="mb-3 text-sm text-slate-600">Clears the attention flag so payments can be attempted again. The failed attempts stay on file.</p>
          {reasonForm("What was reviewed or fixed?", `/api/invoices/${inv.id}/reset-payment-attempts/`, "Reset attempts")}
        </Modal>
      )}
    </section>
  );
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const { data: inv, isLoading, isError } = useQuery({ queryKey: ["invoices", "detail", id], queryFn: () => api.get<any>(`/api/invoices/${id}/`) });

  if (isLoading) return <p className="py-6 text-slate-500">Loading…</p>;
  if (isError || !inv) return <p className="py-6 text-red-700">Invoice not found. <Link className="text-sky-700" to="/invoices">Back to the list</Link></p>;

  const act = async (action: "confirm" | "cancel" | "send", message = "", body?: unknown) => {
    setError(""); setNote("");
    try {
      const fresh = await api.post<any>(`/api/invoices/${id}/${action}/`, body);
      qc.setQueryData(["invoices", "detail", id], fresh);
      qc.invalidateQueries({ queryKey: ["notifications", "timeline"] });
      qc.invalidateQueries({ queryKey: ["invoices", "list"] });
      if (message) setNote(message);
    } catch (e) {
      setError(e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "Could not complete that action.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link className="text-sm text-sky-700" to="/invoices">← Invoices</Link>
        <h1 className="text-xl font-semibold">{inv.number ?? `Draft invoice #${inv.id}`}</h1>
        <StatusBadge status={inv.status} />
        {inv.is_overdue && <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">{inv.days_overdue} days overdue</span>}
        {inv.payment_needs_attention && <span className="rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white">Payment needs attention</span>}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {inv.actions.includes("confirm") && <button className="rounded bg-sky-600 px-3 py-1 text-sm text-white" onClick={() => act("confirm", "Confirmed. The customer has been notified.")}>Confirm</button>}
          {inv.actions.includes("send") && (
            <>
              <button className="rounded border px-3 py-1 text-sm" onClick={() => act("send", "Email queued for the customer.", { channels: ["email"] })}>Send via email</button>
              <button className="rounded border px-3 py-1 text-sm" onClick={() => act("send", "WhatsApp queued if the customer opted in — see the notifications list below.", { channels: ["whatsapp"] })}>Send via WhatsApp</button>
            </>
          )}
          <Link className="rounded border px-3 py-1 text-sm" to={`/invoices/${id}/print`}>Print</Link>
          {inv.actions.includes("cancel") && <ConfirmButton danger label="Cancel invoice" confirmText="Cancel this invoice?" onConfirm={() => act("cancel")} />}
        </div>
      </div>
      {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {note && <p role="status" className="rounded bg-green-50 px-3 py-2 text-sm text-green-800">{note}</p>}

      <dl className="grid gap-4 rounded border bg-white p-4 sm:grid-cols-3">
        <Field label="Customer">{inv.customer_email}</Field>
        <Field label="Subscription"><Link className="text-sky-700" to={`/subscriptions/${inv.subscription}`}>{inv.subscription_number}</Link></Field>
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

      {inv.status !== "draft" && inv.status !== "cancelled" && (
        <PaymentsSection inv={inv} onChanged={() => {
          qc.invalidateQueries({ queryKey: ["invoices"] });
          qc.invalidateQueries({ queryKey: ["payments"] });
        }} />
      )}
      {inv.status !== "draft" && <NotificationTimeline objectType="invoice" objectId={inv.id} />}
    </div>
  );
}
