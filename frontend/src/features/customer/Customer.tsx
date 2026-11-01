import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CheckCircle2, CreditCard, Landmark, Printer, ShieldCheck, Smartphone } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

// Customer self-service: everything here reads endpoints the API already scopes to the caller (a customer only ever
// receives their own rows; drafts are never shown). Paying uses the demo gateway (POST /api/invoices/{id}/pay/).

const Title = ({ children, sub }: { children: string; sub?: string }) => (
  <div>
    <h1 className="text-xl font-semibold">{children}</h1>
    {sub && <p className="text-sm text-slate-500">{sub}</p>}
  </div>
);

const methodName = (m: string) => (m === "upi" ? "UPI" : String(m).replace("_", " "));

const Chips = ({ options, value, onChange, label }: { options: { key: string; label: string }[]; value: string; onChange: (k: string) => void; label: string }) => (
  <div className="flex flex-wrap gap-2" role="group" aria-label={label}>
    {options.map((c) => (
      <button key={c.key} type="button" aria-pressed={value === c.key} onClick={() => onChange(c.key)}
        className={`rounded-full px-3 py-1 text-sm ${value === c.key ? "bg-sky-600 text-white" : "border bg-white text-slate-700"}`}>
        {c.label}
      </button>
    ))}
  </div>
);

/* ---------- My subscriptions ---------- */
const subColumns: Column<any>[] = [
  { key: "number", header: "Subscription", render: (r) => <span className="font-medium">{r.number}</span> },
  { key: "plan_name", header: "Plan" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "start_date", header: "Started" },
  { key: "next_invoice_date", header: "Next invoice", render: (r) => r.next_invoice_date ?? "–" },
  { key: "expiry_date", header: "Ends", render: (r) => r.expiry_date ?? "No end date" },
  { key: "lines_total", header: "Per period", render: (r) => <MoneyText value={r.lines_total} /> },
];

export function MySubscriptions() {
  const [chip, setChip] = useState("all");
  return (
    <div className="space-y-4">
      <Title sub="Every plan you are on, and when you are billed next.">My subscriptions</Title>
      <Chips label="Subscription filters" value={chip} onChange={setChip} options={[{ key: "all", label: "All" }, { key: "active", label: "Active" }, { key: "paused", label: "Paused" }, { key: "closed", label: "Closed" }]} />
      <DataTable queryKey="my-subscriptions" endpoint="/api/subscriptions/" columns={subColumns} params={chip === "all" ? {} : { status: chip }} empty="You have no subscriptions yet." />
    </div>
  );
}

/* ---------- My invoices ---------- */
function Outstanding() {
  const q = useQuery({ queryKey: ["my-summary"], queryFn: () => api.get<any>("/api/dashboard/summary/") });
  const k = q.data?.kpis;
  if (!k) return null;
  const owing = Number(k.outstanding) > 0;
  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4 ${owing ? "border-amber-200 bg-amber-50" : "border-green-200 bg-green-50"}`}>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Outstanding balance</p>
        <p className="text-2xl font-semibold"><MoneyText value={k.outstanding} /></p>
      </div>
      <p className="text-sm text-slate-600">
        {owing ? (k.overdue_count > 0 ? <span className="font-medium text-red-700">{k.overdue_count} overdue · <MoneyText value={k.overdue_amount} /></span> : "Nothing overdue.") : "You're all paid up."}
      </p>
    </div>
  );
}

export function MyInvoices() {
  const navigate = useNavigate();
  const [chip, setChip] = useState("all");
  const params: Record<string, string> = chip === "unpaid" ? { status: "confirmed" } : chip === "paid" ? { status: "paid" } : {};
  const columns: Column<any>[] = [
    { key: "number", header: "Invoice", render: (r) => <Link className="font-medium text-sky-700" to={`/my/invoices/${r.id}`}>{r.number}</Link> },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "invoice_date", header: "Issued" },
    {
      key: "due_date", header: "Due",
      render: (r) => r.is_overdue ? <span className="font-medium text-red-700">{r.due_date} · {r.days_overdue} day{r.days_overdue === 1 ? "" : "s"} overdue</span> : r.due_date,
    },
    { key: "total", header: "Total", render: (r) => <MoneyText value={r.total} /> },
    { key: "amount_due", header: "Balance", render: (r) => <MoneyText value={r.amount_due} /> },
    {
      key: "pay", header: "",
      render: (r) => r.status === "confirmed" && Number(r.amount_due) > 0
        ? <button className="rounded-lg bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-700" onClick={(e) => { e.stopPropagation(); navigate(`/my/pay/${r.id}`); }}>Pay now</button>
        : null,
    },
  ];
  return (
    <div className="space-y-4">
      <Title sub="Invoices issued to you. Pay online or download a copy.">My invoices</Title>
      <Outstanding />
      <Chips label="Invoice filters" value={chip} onChange={setChip} options={[{ key: "all", label: "All" }, { key: "unpaid", label: "Unpaid" }, { key: "paid", label: "Paid" }]} />
      <DataTable queryKey="my-invoices" endpoint="/api/invoices/" columns={columns} params={params} empty="No invoices yet. They appear here after your first billing date." onRowClick={(r: any) => navigate(`/my/invoices/${r.id}`)} />
    </div>
  );
}

/* ---------- One invoice ---------- */
const Row = ({ k, v, bold }: { k: string; v: string; bold?: boolean }) => (
  <div className={`flex justify-between ${bold ? "border-t pt-1 font-semibold" : "text-slate-600"}`}><span>{k}</span><MoneyText value={v} /></div>
);

export function MyInvoiceDetail() {
  const { id } = useParams();
  const q = useQuery({ queryKey: ["my-invoice", id], queryFn: () => api.get<any>(`/api/invoices/${id}/`) });
  if (q.isLoading) return <p className="text-slate-500">Loading…</p>;
  if (q.isError || !q.data) return <p className="text-red-700">We couldn't find that invoice. <Link className="text-sky-700" to="/my/invoices">Back to invoices</Link></p>;
  const inv = q.data;
  const payable = inv.status === "confirmed" && Number(inv.amount_due) > 0;
  return (
    <div className="space-y-5">
      <Link to="/my/invoices" className="text-sm text-sky-700">← My invoices</Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Invoice {inv.number}</h1>
          <StatusBadge status={inv.status} />
        </div>
        <div className="flex gap-2">
          <Link to={`/invoices/${inv.id}/print`} target="_blank" className="inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-1.5 text-sm"><Printer size={15} />Print / PDF</Link>
          {payable && <Link to={`/my/pay/${inv.id}`} className="rounded-lg bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-700">Pay <MoneyText value={inv.amount_due} /></Link>}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[["Subscription", inv.subscription_number], ["Issued", inv.invoice_date], ["Due", inv.due_date], ["Billing period", `${inv.period_start} → ${inv.period_end}`]].map(([k, v]) => (
          <div key={k} className="rounded-xl border bg-white p-3"><dt className="text-xs text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>
        ))}
      </dl>
      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="p-3">Item</th><th className="p-3">Qty</th><th className="p-3 text-right">Unit price</th><th className="p-3 text-right">Tax</th><th className="p-3 text-right">Amount</th></tr></thead>
          <tbody>
            {inv.lines.map((l: any) => (
              <tr key={l.id} className="border-t"><td className="p-3">{l.description}</td><td className="p-3">{l.quantity}</td><td className="p-3 text-right"><MoneyText value={l.unit_price} /></td><td className="p-3 text-right"><MoneyText value={l.line_tax} /></td><td className="p-3 text-right"><MoneyText value={l.line_total} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="ml-auto w-full max-w-xs space-y-1 text-sm">
        <Row k="Subtotal" v={inv.subtotal} />
        {Number(inv.discount_total) > 0 && <Row k="Discount" v={`-${inv.discount_total}`} />}
        <Row k="Tax" v={inv.tax_total} />
        <Row k="Total" v={inv.total} bold />
        <Row k="Paid" v={inv.amount_paid} />
        <Row k="Balance due" v={inv.amount_due} bold />
      </div>
      {inv.payments?.length > 0 && (
        <div>
          <h2 className="mb-2 font-medium">Payments on this invoice</h2>
          <ul className="divide-y rounded-xl border bg-white text-sm">
            {inv.payments.map((p: any) => (
              <li key={p.id} className="flex items-center justify-between gap-3 p-3">
                <span>{p.payment_date} · <span className="capitalize">{methodName(p.method)}</span></span>
                <span className="flex items-center gap-2"><StatusBadge status={p.status} /><span className={p.status === "completed" ? "" : "line-through"}><MoneyText value={p.amount} /></span></span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ---------- Pay an invoice (demo gateway: only the chosen method is sent anywhere) ---------- */
type Method = "card" | "upi" | "bank_transfer";
const METHODS: { key: Method; label: string; Icon: typeof CreditCard }[] = [
  { key: "card", label: "Card", Icon: CreditCard },
  { key: "upi", label: "UPI", Icon: Smartphone },
  { key: "bank_transfer", label: "Net banking", Icon: Landmark },
];
const BANKS = ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank"];
const inputCls = "w-full rounded-lg border px-3 py-2 text-sm";

export function PayInvoice() {
  const { id } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["my-invoice", id], queryFn: () => api.get<any>(`/api/invoices/${id}/`) });
  const [method, setMethod] = useState<Method>("card");
  const [card, setCard] = useState({ number: "", expiry: "", cvc: "", name: "" });
  const [upi, setUpi] = useState("");
  const [bank, setBank] = useState(BANKS[0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<any>(null);

  if (q.isLoading) return <p className="text-slate-500">Loading…</p>;
  if (q.isError || !q.data) return <p className="text-red-700">We couldn't find that invoice. <Link className="text-sky-700" to="/my/invoices">Back to invoices</Link></p>;
  const inv = q.data;

  if (receipt) {
    return (
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-md space-y-4 py-6 text-center">
        <motion.div initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 260, damping: 16 }} className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-green-100 text-green-600">
          <CheckCircle2 size={44} />
        </motion.div>
        <h1 className="text-xl font-semibold">Payment received</h1>
        <p className="text-slate-600">Thank you. <MoneyText value={receipt.payment.amount} /> was paid for invoice {inv.number} by <span className="capitalize">{methodName(receipt.payment.method)}</span> on {receipt.payment.payment_date}.</p>
        <p className="text-xs text-slate-500">Receipt reference #{receipt.payment.id}. A confirmation is sent to your email.</p>
        <div className="flex justify-center gap-2">
          <Link to={`/my/invoices/${inv.id}`} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white">View invoice</Link>
          <Link to="/my/invoices" className="rounded-lg border bg-white px-4 py-2 text-sm">All invoices</Link>
        </div>
      </motion.div>
    );
  }

  if (!(inv.status === "confirmed" && Number(inv.amount_due) > 0)) {
    return (
      <div className="space-y-3">
        <p className="text-slate-700">{inv.status === "paid" ? "This invoice is already paid in full." : "This invoice can't be paid right now."}</p>
        <Link to={`/my/invoices/${inv.id}`} className="text-sky-700">← Back to invoice</Link>
      </div>
    );
  }

  const valid = method === "card"
    ? card.number.replace(/\s/g, "").length >= 12 && /^\d{2}\s*\/\s*\d{2}$/.test(card.expiry) && card.cvc.length >= 3 && card.name.trim().length > 1
    : method === "upi" ? /^[\w.\-]{2,}@[a-zA-Z]{2,}$/.test(upi) : true;

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await new Promise((r) => setTimeout(r, 1100)); // "contacting your bank": the demo gateway answers instantly, this makes the step visible
      await api.get("/api/auth/csrf/");
      const res = await api.post<any>(`/api/invoices/${inv.id}/pay/`, { method }); // only the method leaves the browser; card/UPI details are never sent or stored
      setReceipt(res);
      qc.invalidateQueries({ queryKey: ["my-invoices"] });
      qc.invalidateQueries({ queryKey: ["my-invoice"] });
      qc.invalidateQueries({ queryKey: ["my-summary"] });
      qc.invalidateQueries({ queryKey: ["home"] });
    } catch (e) {
      const b = e instanceof ApiError && e.body && typeof e.body === "object" ? (e.body as Record<string, any>) : null;
      setError(e instanceof ApiError && e.status === 404 ? "Online payment isn't switched on for this site yet. Please contact us to pay." : String(b?.detail ?? b?.message ?? "The payment couldn't be completed. Please try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-3xl gap-6 md:grid-cols-5">
      <div className="space-y-4 md:col-span-3">
        <Link to={`/my/invoices/${inv.id}`} className="text-sm text-sky-700">← Invoice {inv.number}</Link>
        <Title sub="Choose how you'd like to pay.">Pay invoice</Title>
        <div className="grid grid-cols-3 gap-2" role="tablist" aria-label="Payment method">
          {METHODS.map(({ key, label, Icon }) => (
            <button key={key} role="tab" aria-selected={method === key} type="button" onClick={() => setMethod(key)}
              className={`flex flex-col items-center gap-1 rounded-xl border px-3 py-3 text-sm font-medium ${method === key ? "border-sky-600 bg-sky-50 text-sky-800" : "bg-white text-slate-700"}`}>
              <Icon size={20} />{label}
            </button>
          ))}
        </div>

        {method === "card" && (
          <div className="space-y-3">
            <button type="button" onClick={() => setCard({ number: "4242 4242 4242 4242", expiry: "12/30", cvc: "123", name: "Demo Customer" })} className="text-xs text-sky-700 underline">Fill with a test card</button>
            <label className="block text-sm">Card number<input className={inputCls} inputMode="numeric" autoComplete="off" placeholder="4242 4242 4242 4242" value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value.replace(/[^\d ]/g, "").slice(0, 23) })} /></label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm">Expiry<input className={inputCls} autoComplete="off" placeholder="MM/YY" value={card.expiry} onChange={(e) => setCard({ ...card, expiry: e.target.value.replace(/[^\d/ ]/g, "").slice(0, 7) })} /></label>
              <label className="block text-sm">CVC<input className={inputCls} type="password" inputMode="numeric" autoComplete="off" placeholder="123" value={card.cvc} onChange={(e) => setCard({ ...card, cvc: e.target.value.replace(/\D/g, "").slice(0, 4) })} /></label>
            </div>
            <label className="block text-sm">Name on card<input className={inputCls} autoComplete="off" value={card.name} onChange={(e) => setCard({ ...card, name: e.target.value })} /></label>
          </div>
        )}
        {method === "upi" && (
          <label className="block text-sm">UPI ID<input className={inputCls} autoComplete="off" placeholder="name@bank" value={upi} onChange={(e) => setUpi(e.target.value.trim())} /></label>
        )}
        {method === "bank_transfer" && (
          <label className="block text-sm">Your bank<select className={inputCls} value={bank} onChange={(e) => setBank(e.target.value)}>{BANKS.map((b) => <option key={b}>{b}</option>)}</select></label>
        )}

        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
        <button type="button" disabled={!valid || busy} onClick={submit} className="w-full rounded-xl bg-sky-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:opacity-50">
          {busy ? "Processing securely…" : <>Pay <MoneyText value={inv.amount_due} /></>}
        </button>
        <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900"><ShieldCheck size={16} className="mt-px shrink-0" />Demo payment: no real money moves and card or UPI details are never sent or stored. Don't enter real card details.</p>
      </div>

      <aside className="md:col-span-2">
        <div className="space-y-2 rounded-2xl border bg-white p-4 text-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Order summary</p>
          <Row k={`Invoice ${inv.number}`} v={inv.total} />
          {Number(inv.amount_paid) > 0 && <Row k="Already paid" v={`-${inv.amount_paid}`} />}
          <Row k="To pay now" v={inv.amount_due} bold />
          <p className="pt-1 text-xs text-slate-500">Due {inv.due_date}{inv.is_overdue ? ` · ${inv.days_overdue} day${inv.days_overdue === 1 ? "" : "s"} overdue` : ""}</p>
        </div>
      </aside>
    </div>
  );
}

/* ---------- Payment history ---------- */
const payColumns: Column<any>[] = [
  { key: "payment_date", header: "Date" },
  { key: "invoice_number", header: "Invoice", render: (r) => <Link className="text-sky-700" to={`/my/invoices/${r.invoice}`}>{r.invoice_number ?? `#${r.invoice}`}</Link> },
  { key: "method", header: "Method", render: (r) => <span className="capitalize">{methodName(r.method)}</span> },
  { key: "amount", header: "Amount", render: (r) => <span className={r.status === "completed" ? "" : "line-through"}><MoneyText value={r.amount} /></span> },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
];

export function MyPayments() {
  return (
    <div className="space-y-4">
      <Title sub="Every payment made against your invoices.">Payment history</Title>
      <DataTable queryKey="my-payments" endpoint="/api/payments/" columns={payColumns} empty="No payments yet." />
    </div>
  );
}
