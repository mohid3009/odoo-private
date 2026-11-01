import PageLoader from "../../components/PageLoader";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import ConfirmButton from "../../components/ConfirmButton";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";
import NotificationTimeline from "./NotificationTimeline";
import SubscriptionForm from "./SubscriptionForm";

// Which button each server-offered action shows. The server decides what is offered (`actions`) and re-checks it on click.
const LABEL: Record<string, string> = {
  quotation: "Send quotation", draft: "Back to draft", confirmed: "Confirm", active: "Activate", paused: "Pause", closed: "Close", renew: "Renew",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs text-slate-500">{label}</dt><dd>{children}</dd></div>;
}

// Attach/detach a subscription-scope discount. Product discounts apply by themselves and are not listed here.
function DiscountControl({ sub, onChange, onError }: { sub: any; onChange: (fresh: any) => void; onError: (m: string) => void }) {
  const [choice, setChoice] = useState("");
  const rules = useQuery({
    queryKey: ["options", "/api/discounts/?scope=subscription"],
    queryFn: () => api.get<any>("/api/discounts/?scope=subscription&is_active=true&page_size=200"),
  });
  const call = async (run: () => Promise<any>) => {
    onError("");
    try { onChange(await run()); setChoice(""); }
    catch (e) { onError(e instanceof ApiError && ((e.body as any)?.detail || (e.body as any)?.discount) ? String((e.body as any).detail ?? (e.body as any).discount) : "Could not change the discount."); }
  };
  return (
    <section className="flex flex-wrap items-center gap-3 rounded border bg-white p-4 text-sm" aria-label="Discount">
      <span className="font-medium">Discount</span>
      {sub.discount ? (
        <>
          <span className="rounded bg-green-100 px-2 py-0.5 text-green-800">{sub.discount_name}</span>
          <button className="rounded border px-3 py-1" onClick={() => call(() => api.del(`/api/subscriptions/${sub.id}/discount/`))}>Detach</button>
          <span className="text-xs text-slate-500">Applies from the next invoice.</span>
        </>
      ) : (
        <span className="text-slate-500">none attached</span>
      )}
      <select aria-label="Choose a discount" className="rounded border px-2 py-1" value={choice} onChange={(e) => setChoice(e.target.value)}>
        <option value="">{sub.discount ? "Replace with…" : "Attach a discount…"}</option>
        {rules.data?.results.map((d: any) => <option key={d.id} value={d.id}>{d.name} ({d.type === "percent" ? `${Number(d.value)}%` : `₹${d.value}`})</option>)}
      </select>
      <button className="rounded bg-sky-600 px-3 py-1 text-white disabled:opacity-50" disabled={!choice}
        onClick={() => call(() => api.post(`/api/subscriptions/${sub.id}/discount/`, { discount: Number(choice) }))}>Attach</button>
    </section>
  );
}

export default function SubscriptionDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const { data: sub, isLoading, isError } = useQuery({ queryKey: ["subscriptions", "detail", id], queryFn: () => api.get<any>(`/api/subscriptions/${id}/`) });

  if (isLoading) return <PageLoader />;
  if (isError || !sub) return <p className="py-6 text-red-700">Subscription not found. <Link className="text-sky-700" to="/subscriptions">Back to the list</Link></p>;

  const refresh = (fresh: any) => {
    qc.setQueryData(["subscriptions", "detail", id], fresh);
    qc.invalidateQueries({ queryKey: ["subscriptions", "list"] });
  };
  const run = async (action: string) => {
    setError("");
    try {
      refresh(action === "renew" ? await api.post(`/api/subscriptions/${id}/renew/`) : await api.post(`/api/subscriptions/${id}/transition/`, { to: action }));
    } catch (e) {
      setError(e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "Could not complete that action.");
    }
  };
  const label = (a: string) => (a === "active" && sub.status === "paused" ? "Resume" : LABEL[a] ?? a);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Link className="text-sm text-sky-700" to="/subscriptions">← Subscriptions</Link>
        <h1 className="text-xl font-semibold">{sub.number}</h1>
        <StatusBadge status={sub.status} />
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {sub.status === "draft" && !editing && <button className="rounded border px-3 py-1 text-sm" onClick={() => setEditing(true)}>Edit</button>}
          {sub.actions.map((a: string) =>
            a === "closed"
              ? <ConfirmButton key={a} danger label="Close" confirmText="Close this subscription?" onConfirm={() => run(a)} />
              : <button key={a} className="rounded bg-sky-600 px-3 py-1 text-sm text-white" onClick={() => run(a)}>{label(a)}</button>)}
        </div>
      </div>
      {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {editing ? (
        <div className="max-w-3xl rounded border bg-white p-5">
          <SubscriptionForm initial={sub} onCancel={() => setEditing(false)} onSaved={(fresh) => { refresh(fresh); setEditing(false); }} />
        </div>
      ) : (
        <>
          <dl className="grid gap-4 rounded border bg-white p-4 sm:grid-cols-3">
            <Field label="Customer">{sub.customer_email}</Field>
            <Field label="Plan">{sub.plan_name}</Field>
            <Field label="Payment term">{sub.payment_term_name}</Field>
            <Field label="Start">{sub.start_date}</Field>
            <Field label="Expiry">{sub.expiry_date ?? "—"}</Field>
            <Field label="Next invoice">{sub.next_invoice_date ?? "—"}</Field>
            <Field label="Quotation valid until">{sub.quotation_valid_until ?? "—"}</Field>
            <Field label="Notes">{sub.notes || "—"}</Field>
          </dl>

          {sub.status !== "closed" && <DiscountControl sub={sub} onChange={refresh} onError={setError} />}

          <div className="overflow-x-auto rounded border bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>{["Description", "Qty", "Unit price", "Amount"].map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {sub.lines.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-slate-500">No lines yet.</td></tr>}
                {sub.lines.map((l: any) => (
                  <tr key={l.id} className="border-t">
                    <td className="px-3 py-2">{l.description}</td>
                    <td className="px-3 py-2">{l.quantity}</td>
                    <td className="px-3 py-2"><MoneyText value={l.unit_price} /></td>
                    <td className="px-3 py-2"><MoneyText value={l.amount} /></td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t bg-slate-50 font-medium">
                  <td className="px-3 py-2" colSpan={3}>Subtotal (before tax)</td>
                  <td className="px-3 py-2"><MoneyText value={sub.lines_total} /></td>
                </tr>
              </tfoot>
            </table>
          </div>

          <section>
            <h2 className="mb-2 font-semibold">Status history</h2>
            <ol className="space-y-1 border-l-2 pl-4 text-sm">
              <li className="text-slate-500">Created {new Date(sub.created_at).toLocaleString()}</li>
              {sub.status_log.map((l: any, i: number) => (
                <li key={i}>
                  <StatusBadge status={l.from_status} /> → <StatusBadge status={l.to_status} />
                  <span className="ml-2 text-slate-500">by {l.by_user_email} · {new Date(l.at).toLocaleString()}</span>
                </li>
              ))}
            </ol>
          </section>
          <NotificationTimeline objectType="subscription" objectId={sub.id} />
        </>
      )}
    </div>
  );
}
