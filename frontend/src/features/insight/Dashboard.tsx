import { ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import MoneyText from "../../components/MoneyText";

// Finance dashboard (S7): every number is computed server-side by GET /api/dashboard/summary/ (docs/API.md Phase 8).
interface Summary {
  filters: { from: string; to: string };
  kpis: Record<"mrr" | "arr" | "revenue_collected" | "invoiced" | "outstanding" | "overdue_amount", string> & { active_subscriptions: number; overdue_count: number };
  by_plan: { plan_id: number; plan_name: string; billing_period: string; active_subscriptions: number; mrr: string; invoiced: string; collected: string }[];
  by_month: { month: string; invoiced: string; collected: string }[];
  overdue: Page<{ id: number; number: string; customer_email: string; subscription_number: string; plan_name: string; due_date: string; days_overdue: number; amount_due: string }>;
}

const STATUSES = ["draft", "quotation", "confirmed", "active", "paused", "closed"];
const field = "rounded border px-2 py-1 text-sm";
const th = "px-3 py-2 font-medium";
const td = "px-3 py-2";

function Card({ label, children, to }: { label: string; children: ReactNode; to?: string }) {
  const body = (
    <div className="rounded border bg-white p-4">
      <p className="text-xs uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{children}</p>
    </div>
  );
  return to ? <Link to={to} className="block rounded hover:ring-2 hover:ring-indigo-200">{body}</Link> : body;
}

// Display only: a bar's width is a ratio of two API strings, never a money result (rule 5).
function Bar({ value, max, color }: { value: string; max: number; color: string }) {
  return <div className={`h-2 rounded ${color}`} style={{ width: `${max > 0 ? (Number(value) / max) * 100 : 0}%` }} />;
}

export default function Dashboard() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [customerText, setCustomerText] = useState("");
  const [page, setPage] = useState(1);
  const set = (k: string, v: string) => {
    setPage(1);
    setFilters((f) => { const n = { ...f, [k]: v }; if (!v) delete n[k]; return n; });
  };

  const plans = useQuery({ queryKey: ["options", "/api/plans/"], queryFn: () => api.get<Page<any>>("/api/plans/?page_size=200") });
  const customers = useQuery({
    queryKey: ["options", "/api/customers/", customerText],
    queryFn: () => api.get<Page<any>>(`/api/customers/?${new URLSearchParams({ search: customerText })}`),
    enabled: customerText.length >= 2,
  });
  const qs = new URLSearchParams({ ...filters, page: String(page) }).toString();
  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["dashboard", filters, page],
    queryFn: () => api.get<Summary>(`/api/dashboard/summary/?${qs}`),
    placeholderData: (prev) => prev,
  });

  const pickCustomer = (text: string) => {
    setCustomerText(text);
    const hit = customers.data?.results.find((c) => c.email === text);
    if (hit) set("customer", String(hit.id));
    else if (filters.customer) set("customer", "");
  };
  const maxMonth = Math.max(0, ...(data?.by_month ?? []).flatMap((m) => [Number(m.invoiced), Number(m.collected)]));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-2">
        <h1 className="mr-auto text-xl font-semibold">Finance dashboard</h1>
        <label className="text-xs text-slate-500">From<br />
          <input type="date" aria-label="From" className={field} value={filters.from ?? data?.filters.from ?? ""} onChange={(e) => set("from", e.target.value)} />
        </label>
        <label className="text-xs text-slate-500">To<br />
          <input type="date" aria-label="To" className={field} value={filters.to ?? data?.filters.to ?? ""} onChange={(e) => set("to", e.target.value)} />
        </label>
        <label className="text-xs text-slate-500">Customer<br />
          <input list="dash-customers" aria-label="Customer" placeholder="Type an email…" className={field} value={customerText} onChange={(e) => pickCustomer(e.target.value)} />
          <datalist id="dash-customers">{customers.data?.results.map((c) => <option key={c.id} value={c.email}>{c.name}</option>)}</datalist>
        </label>
        <label className="text-xs text-slate-500">Plan<br />
          <select aria-label="Plan" className={field} value={filters.plan ?? ""} onChange={(e) => set("plan", e.target.value)}>
            <option value="">All plans</option>
            {plans.data?.results.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-500">Subscription status<br />
          <select aria-label="Subscription status" className={field} value={filters.status ?? ""} onChange={(e) => set("status", e.target.value)}>
            <option value="">All</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <button className="rounded border px-3 py-1 text-sm" onClick={() => { setFilters({}); setCustomerText(""); setPage(1); }}>Reset</button>
      </div>

      {isLoading && <p className="py-6 text-slate-500">Loading…</p>}
      {isError && <p className="py-6 text-red-700">Could not load the dashboard: {JSON.stringify((error as any)?.body ?? "")}</p>}
      {data && (
        <div className={`space-y-5 ${isFetching ? "opacity-70" : ""}`}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Card label="Active subscriptions" to="/subscriptions?status=active">{data.kpis.active_subscriptions}</Card>
            <Card label="MRR"><MoneyText value={data.kpis.mrr} /></Card>
            <Card label="ARR"><MoneyText value={data.kpis.arr} /></Card>
            <Card label="Revenue collected"><MoneyText value={data.kpis.revenue_collected} /></Card>
            <Card label="Invoiced"><MoneyText value={data.kpis.invoiced} /></Card>
            <Card label="Outstanding" to="/invoices?status=confirmed"><MoneyText value={data.kpis.outstanding} /></Card>
            <Card label={`Overdue (${data.kpis.overdue_count})`} to="/invoices?status=overdue"><span className="text-red-700"><MoneyText value={data.kpis.overdue_amount} /></span></Card>
          </div>
          <p className="text-xs text-slate-500">
            Revenue collected and invoiced cover {data.filters.from} → {data.filters.to}; outstanding, overdue, MRR and active counts are as of today.
          </p>

          <div className="grid gap-5 lg:grid-cols-2">
            <section>
              <h2 className="mb-2 font-semibold">By plan</h2>
              <div className="overflow-x-auto rounded border bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600"><tr>{["Plan", "Active", "MRR", "Invoiced", "Collected"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {data.by_plan.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-slate-500">No data for these filters.</td></tr>}
                    {data.by_plan.map((p) => (
                      <tr key={p.plan_id} className="border-t">
                        <td className={td}><Link className="text-indigo-700" to={`/subscriptions?plan=${p.plan_id}`}>{p.plan_name}</Link> <span className="text-xs text-slate-500">{p.billing_period}</span></td>
                        <td className={td}>{p.active_subscriptions}</td>
                        <td className={td}><MoneyText value={p.mrr} /></td>
                        <td className={td}><MoneyText value={p.invoiced} /></td>
                        <td className={td}><MoneyText value={p.collected} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section>
              <h2 className="mb-2 font-semibold">
                By month <span className="text-xs font-normal"><span className="text-indigo-600">■</span> invoiced <span className="text-green-600">■</span> collected</span>
              </h2>
              <div className="overflow-x-auto rounded border bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600"><tr>{["Month", "Invoiced", "Collected", ""].map((h, i) => <th key={i} className={th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {data.by_month.map((m) => (
                      <tr key={m.month} className="border-t">
                        <td className={td}>{m.month}</td>
                        <td className={td}><MoneyText value={m.invoiced} /></td>
                        <td className={td}><MoneyText value={m.collected} /></td>
                        <td className="w-1/3 space-y-1 px-3 py-2"><Bar value={m.invoiced} max={maxMonth} color="bg-indigo-500" /><Bar value={m.collected} max={maxMonth} color="bg-green-500" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <section>
            <h2 className="mb-2 font-semibold">Overdue invoices</h2>
            <div className="overflow-x-auto rounded border bg-white">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>{["Invoice", "Customer", "Subscription", "Plan", "Due", "Days overdue", "Balance"].map((h) => <th key={h} className={th}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {data.overdue.results.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-slate-500">Nothing overdue.</td></tr>}
                  {data.overdue.results.map((r) => (
                    <tr key={r.id} className="border-t">
                      <td className={td}><Link className="font-medium text-indigo-700" to={`/invoices/${r.id}`}>{r.number}</Link></td>
                      <td className={td}>{r.customer_email}</td>
                      <td className={td}>{r.subscription_number}</td>
                      <td className={td}>{r.plan_name}</td>
                      <td className={td}>{r.due_date}</td>
                      <td className={`${td} font-medium text-red-700`}>{r.days_overdue}</td>
                      <td className={td}><MoneyText value={r.amount_due} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
              <span>{data.overdue.count} overdue</span>
              <div className="flex items-center gap-2">
                <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page} / {Math.max(1, Math.ceil(data.overdue.count / 25))}</span>
                <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={!data.overdue.next} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
