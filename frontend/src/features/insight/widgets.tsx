import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, ChevronLeft, ChevronRight, ChevronsUpDown, CreditCard, FileText, Maximize2,
  Package, Percent, Plus, Receipt, Repeat, Sparkles, UserCircle, X, Zap, type LucideIcon,
} from "lucide-react";
import { api, type Health } from "../../api/client";
import type { Page } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { BarRise, Donut, Gauge, Heat, Sparkline, TrendChart } from "../../components/charts/charts";
import MoneyText from "../../components/MoneyText";
import { CountUp, Empty, ErrorState, Glass, InfoTip, Segmented, Skeleton, WidgetCard } from "../../components/ui/glass";
import { activitySeed, bars, daySalt, HEAT_COLS, HEAT_ROWS, heat, nextActivity, spark, trend, useMock, type Activity, type Period } from "../../data/mock";
import { toCents } from "../../lib/money";
import { useRange } from "../../lib/theme";

export type Counts = Record<"active" | "paused" | "pending" | "open" | "overdue" | "paid", number | undefined>;

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1 });
const fmtInr = (n: number) => inr.format(n);

/* ---------- 1. KPI ---------- */
export function Kpi({ Icon, label, value, format, delta, seed, color: baseColor, info, className, highlight }: {
  Icon: LucideIcon; label: string; value: number | undefined; format?: (n: number) => string;
  delta: number; seed: number; color: string; info: string; className: string; highlight?: boolean; // highlight = the filled green tile
}) {
  const up = delta >= 0;
  const color = highlight ? "#ffffff" : baseColor;
  const s = useMock(["spark", seed], () => spark(seed), 300);
  return (
    <WidgetCard className={highlight ? `${className} hi` : className}>
      <div className="flex items-start justify-between">
        <span className="grid h-11 w-11 place-items-center rounded-full text-white" style={{ background: highlight ? "rgba(255,255,255,0.28)" : `linear-gradient(135deg, ${color}, ${color}bb)`, boxShadow: highlight ? "none" : `0 6px 18px ${color}66` }}>
          <Icon size={20} />
        </span>
        <span title="Sample trend" className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${up ? "pill-ok" : "pill-bad"}`}>
          {up ? <ArrowUp size={12} /> : <ArrowDown size={12} />}{Math.abs(delta).toFixed(1)}%
        </span>
      </div>
      <p className="mt-4 flex items-center gap-1.5 text-[13px] font-semibold text-fg2">{label}<InfoTip text={info} /></p>
      <div className="mt-1 flex items-end justify-between gap-3">
        <div className="shrink-0 tabular-nums text-4xl font-semibold tracking-tight xl:text-[38px] 2xl:text-[44px]">
          {value === undefined ? <Skeleton className="h-10 w-20" /> : <CountUp value={value} format={format} />}
        </div>
        <div className="h-10 min-w-0 max-w-24 flex-1 overflow-hidden">{s.data && <Sparkline data={s.data} color={color} />}</div>
      </div>
    </WidgetCard>
  );
}

/* ---------- 2. Trend (click the expand icon for the detail view) ---------- */
const PERIODS = (["Day", "Week", "Month", "Year"] as Period[]).map((value) => ({ value, label: value }));

export function TrendWidget({ className }: { className: string }) {
  const { range, endDate } = useRange();
  const [period, setPeriod] = useState<Period>("Month");
  const [open, setOpen] = useState(false);
  const q = useMock(["trend", period, range, endDate], () => trend(period, range, daySalt(endDate)), 450);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open]);

  const vals = q.data?.map((d) => d.value) ?? [];
  const sum = vals.reduce((a, b) => a + b, 0);
  const chart = (h: string) =>
    q.isError ? <ErrorState onRetry={() => q.refetch()} /> : q.data ? <div className={h}><TrendChart data={q.data} format={fmtInr} /></div> : <Skeleton className={h} />;

  return (
    <div className={`${className} min-h-[380px]`}>
      {!open && (
        <WidgetCard
          layoutId="trend-card" className="h-full" title="Revenue trend" info="Revenue collected over the selected period (sample data)."
          controls={
            <div className="flex items-center gap-2">
              <Segmented id="trend-seg" options={PERIODS} value={period} onChange={setPeriod} />
              <button aria-label="Expand revenue trend" onClick={() => setOpen(true)} className="tap grid h-8 w-8 place-items-center rounded-full text-fg2 hover:bg-[var(--sel)] hover:text-fg"><Maximize2 size={15} /></button>
            </div>
          }
        >
          <div className="flex h-full flex-col">
            <p className="tabular-nums text-3xl font-semibold tracking-tight"><CountUp value={sum} format={fmtInr} /> <span className="font-sans text-xs font-normal text-muted">sample data</span></p>
            {chart("mt-3 min-h-[240px] flex-1")}
          </div>
        </WidgetCard>
      )}
      <AnimatePresence>
        {open && (
          <motion.div className="no-print fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={() => setOpen(false)}>
            <motion.div layoutId="trend-card" className="w-full max-w-4xl" role="dialog" aria-modal="true" aria-label="Revenue trend detail" onMouseDown={(e) => e.stopPropagation()}>
              <Glass flat className="p-6">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-[13px] font-semibold text-fg2">Revenue trend · detail</h2>
                  <div className="flex items-center gap-2">
                    <Segmented id="trend-seg-modal" options={PERIODS} value={period} onChange={setPeriod} />
                    <button autoFocus aria-label="Close detail view" onClick={() => setOpen(false)} className="tap grid h-8 w-8 place-items-center rounded-full hover:bg-[var(--sel)]"><X size={16} /></button>
                  </div>
                </div>
                <div className="mb-4 grid grid-cols-3 gap-3">
                  {[["Peak", Math.max(...vals, 0)], ["Low", Math.min(...(vals.length ? vals : [0]))], ["Average", vals.length ? Math.round(sum / vals.length) : 0]].map(([k, v]) => (
                    <div key={k as string} className="rounded-[12px] border border-[var(--glass-border)] bg-[var(--tile)] p-3">
                      <p className="text-[11px] text-fg2">{k}</p>
                      <p className="tabular-nums text-xl font-semibold">{fmtInr(v as number)}</p>
                    </div>
                  ))}
                </div>
                {chart("h-[340px]")}
              </Glass>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ---------- 3. Subscription mix (real) ---------- */
export function StatusDonut({ n, className }: { n: Counts; className: string }) {
  const ready = n.active !== undefined;
  const segs = [
    { label: "Active", value: n.active ?? 0, color: "#0A84FF" },
    { label: "Paused", value: n.paused ?? 0, color: "#FF9F0A" },
    { label: "Quotation", value: n.pending ?? 0, color: "#64D2FF" },
  ];
  const empty = ready && segs.every((s) => s.value === 0);
  return (
    <WidgetCard className={className} title="Subscriptions" info="Share of subscriptions by status. Hover a segment to inspect it.">
      {!ready ? <Skeleton className="mx-auto h-[200px] w-[200px] !rounded-full" /> : empty ? <Empty text="No subscriptions yet." /> : <Donut segments={segs} centerLabel="Total" />}
    </WidgetCard>
  );
}

/* ---------- 4. Collection gauge (real) ---------- */
export function CollectionGauge({ n, className }: { n: Counts; className: string }) {
  const issued = (n.open ?? 0) + (n.paid ?? 0);
  const pct = issued ? Math.round(((n.paid ?? 0) / issued) * 100) : 0;
  return (
    <WidgetCard className={className} title="Collection rate" info="Paid invoices as a share of all issued (open + paid) invoices.">
      {n.paid === undefined ? <Skeleton className="mx-auto h-[160px] w-[160px] !rounded-full" /> : <Gauge value={pct} label={`${n.paid} of ${issued} invoices paid`} />}
    </WidgetCard>
  );
}

/* ---------- 5. Bars ---------- */
export function InvoicesBars({ className }: { className: string }) {
  const { range, endDate } = useRange();
  const q = useMock(["bars", range, endDate], () => bars(range, daySalt(endDate)), 500);
  return (
    <WidgetCard className={className} title="Invoices issued" info="Invoices generated per week (sample data).">
      {q.isError ? <ErrorState onRetry={() => q.refetch()} /> : q.data ? <BarRise data={q.data} format={(v) => String(v)} /> : <Skeleton className="h-[170px] w-full" />}
    </WidgetCard>
  );
}

/* ---------- 6. Heatmap ---------- */
export function PaymentHeat({ className }: { className: string }) {
  const { range, endDate } = useRange();
  const q = useMock(["heat", range, endDate], () => heat(range, daySalt(endDate)), 600);
  return (
    <WidgetCard className={className} title="Payment activity" info="When customers pay: weekday by 2-hour block (sample data).">
      {q.data ? <Heat data={q.data} rows={HEAT_ROWS} cols={HEAT_COLS} /> : <Skeleton className="h-[200px] w-full" />}
    </WidgetCard>
  );
}

/* ---------- 8. Activity feed ---------- */
const KIND: Record<Activity["kind"], { Icon: LucideIcon; cls: string }> = {
  payment: { Icon: CheckCircle2, cls: "bg-gradient-to-br from-[#4ade80] to-[#16a34a] text-white shadow-[0_6px_14px_rgba(34,197,94,0.45)]" },
  invoice: { Icon: FileText, cls: "bg-gradient-to-br from-[#60a5fa] to-[#2563eb] text-white shadow-[0_6px_14px_rgba(59,130,246,0.45)]" },
  renewal: { Icon: Repeat, cls: "bg-gradient-to-br from-[#a78bfa] to-[#7c3aed] text-white shadow-[0_6px_14px_rgba(139,92,246,0.45)]" },
  failed: { Icon: AlertTriangle, cls: "bg-gradient-to-br from-[#fb7185] to-[#e11d48] text-white shadow-[0_6px_14px_rgba(244,63,94,0.45)]" },
};
function rel(at: number) {
  const m = Math.max(0, Math.round((Date.now() - at) / 60000));
  return m < 1 ? "just now" : m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`;
}

export function ActivityFeed({ className }: { className: string }) {
  const seed = useMock(["activity"], activitySeed, 600);
  const [extra, setExtra] = useState<Activity[]>([]);
  const [, tick] = useState(0);
  useEffect(() => {
    const a = setInterval(() => setExtra((e) => [nextActivity(), ...e].slice(0, 4)), 9000); // simulated live events
    const b = setInterval(() => tick((x) => x + 1), 30000); // refresh relative times
    return () => { clearInterval(a); clearInterval(b); };
  }, []);
  const items = [...extra, ...(seed.data ?? [])].slice(0, 6);
  return (
    <WidgetCard className={className} title="Activity" info="Latest billing events (sample feed, a new one slides in every few seconds).">
      {!seed.data ? (
        <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
      ) : (
        <ul className="relative space-y-3 before:absolute before:bottom-2 before:left-[17px] before:top-2 before:w-px before:bg-[var(--glass-border)]">
          <AnimatePresence initial={false} mode="popLayout">
            {items.map((a) => {
              const { Icon, cls } = KIND[a.kind];
              return (
                <motion.li key={a.id} layout initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }} className="relative flex items-center gap-3">
                  <span className={`relative grid h-9 w-9 shrink-0 place-items-center rounded-full ${cls}`}><Icon size={16} /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{a.text}</p>
                    <p className="text-xs text-muted">{rel(a.at)}</p>
                  </div>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </WidgetCard>
  );
}

/* ---------- 9. Invoices table (real) ---------- */
interface InvoiceRow { id: number; number: string; status: string; due_date: string; total: string; amount_paid: string; customer_email: string }
type SortKey = "number" | "due_date" | "total";
const PILL: Record<string, string> = { paid: "pill-ok", confirmed: "pill-info", draft: "pill-neutral", cancelled: "pill-bad" };
const PAGE = 5;

export function InvoicesTable({ className }: { className: string }) {
  const { user } = useAuth();
  const staff = user?.role !== "customer";
  const q = useQuery({ queryKey: ["home", "invoices"], queryFn: () => api.get<Page<InvoiceRow>>("/api/invoices/?ordering=-invoice_date&page_size=25") });
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);

  const rows = [...(q.data?.results ?? [])];
  if (sort) {
    const { key, dir } = sort;
    rows.sort((a, b) =>
      dir * (key === "total" ? (toCents(a.total) ?? 0) - (toCents(b.total) ?? 0) : String(a[key] ?? "").localeCompare(String(b[key] ?? ""))));
  }
  const shown = rows.slice(page * PAGE, page * PAGE + PAGE);
  const th = (key: SortKey, label: string, right?: boolean) => (
    <th scope="col" aria-sort={sort?.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={`px-3 py-2 font-medium ${right ? "text-right" : "text-left"}`}>
      <button className="tap inline-flex items-center gap-1 hover:text-fg" onClick={() => setSort((s) => ({ key, dir: s?.key === key && s.dir === 1 ? -1 : 1 }))}>
        {label}<ChevronsUpDown size={12} />
      </button>
    </th>
  );

  return (
    <WidgetCard className={className} title="Recent invoices" info="Your latest invoices. Click a column heading to sort." controls={staff && <Link to="/invoices" className="tap rounded-full bg-[var(--sel)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--sel)]">View all</Link>}>
      {q.isError ? <ErrorState onRetry={() => q.refetch()} /> : q.isLoading ? (
        <div className="space-y-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}</div>
      ) : rows.length === 0 ? (
        <Empty Icon={Receipt} text="No invoices yet. They appear after the first billing run." />
      ) : (
        <>
          <div className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-[var(--sticky)] text-[11px] text-fg2">
                <tr>{th("number", "Invoice")}<th scope="col" className="px-3 py-2 text-left font-medium">Status</th>{th("due_date", "Due")}<th scope="col" className="hidden px-3 py-2 text-left font-medium 2xl:table-cell">Paid</th>{th("total", "Total", true)}</tr>
              </thead>
              <tbody>
                {shown.map((i) => {
                  const t = toCents(i.total) ?? 0;
                  const p = t > 0 ? Math.min(100, Math.round(((toCents(i.amount_paid) ?? 0) * 100) / t)) : 0; // display width only
                  return (
                    <tr key={i.id} className="border-t border-[var(--glass-border)] transition-colors hover:bg-[var(--tile)]">
                      <td className="px-3 py-3">
                        <p className="tabular-nums font-medium">{staff ? <Link to={`/invoices/${i.id}`} className="hover:text-accent">{i.number || "Draft"}</Link> : i.number || "Draft"}</p>
                        {staff && <p className="max-w-[160px] truncate text-xs text-muted">{i.customer_email}</p>}
                      </td>
                      <td className="px-3 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${PILL[i.status] ?? "pill-neutral"}`}>{i.status}</span></td>
                      <td className="whitespace-nowrap px-3 py-3 text-fg2">{i.due_date}</td>
                      <td className="hidden px-3 py-3 2xl:table-cell"><div className="h-1.5 w-20 rounded-full bg-[var(--grid)]"><div className="h-full rounded-full bg-gradient-to-r from-[#30D158] to-[#7CEB9B]" style={{ width: `${p}%` }} /></div></td>
                      <td className="px-3 py-3 text-right tabular-nums font-semibold"><MoneyText value={i.total} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-fg2">
            <span>{page * PAGE + 1}–{Math.min(rows.length, page * PAGE + PAGE)} of {rows.length}</span>
            <div className="flex gap-1">
              <button aria-label="Previous page" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="tap grid h-8 w-8 place-items-center rounded-full hover:bg-[var(--sel)] disabled:opacity-30"><ChevronLeft size={16} /></button>
              <button aria-label="Next page" disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage((p) => p + 1)} className="tap grid h-8 w-8 place-items-center rounded-full hover:bg-[var(--sel)] disabled:opacity-30"><ChevronRight size={16} /></button>
            </div>
          </div>
        </>
      )}
    </WidgetCard>
  );
}

/* ---------- 10. Quick actions (magnetic) ---------- */
function Magnetic({ children }: { children: ReactNode }) {
  const x = useMotionValue(0), y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 220, damping: 16 }), sy = useSpring(y, { stiffness: 220, damping: 16 });
  return (
    <motion.div
      style={{ x: sx, y: sy }} whileHover={{ scale: 1.04 }}
      onMouseMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); x.set((e.clientX - r.left - r.width / 2) * 0.25); y.set((e.clientY - r.top - r.height / 2) * 0.25); }}
      onMouseLeave={() => { x.set(0); y.set(0); }}
    >
      {children}
    </motion.div>
  );
}

const STAFF_ACTIONS = [
  { to: "/subscriptions/new", label: "New subscription", Icon: Plus },
  { to: "/billing", label: "Run billing", Icon: Zap },
  { to: "/payments", label: "Payments", Icon: CreditCard },
  { to: "/discounts", label: "Discounts", Icon: Percent },
  { to: "/invoices", label: "Invoices", Icon: Receipt },
  { to: "/catalog", label: "Catalog", Icon: Package },
];
export function QuickActions({ className }: { className: string }) {
  const { user } = useAuth();
  const items = user?.role === "customer" ? [{ to: "/profile", label: "Edit profile", Icon: UserCircle }] : STAFF_ACTIONS;
  return (
    <WidgetCard className={className} title="Quick actions" info="Shortcuts to the things you do most.">
      <div className="grid grid-cols-2 gap-3 [&_a]:min-w-0 [&_a]:break-words [&_a]:px-2">
        {items.map(({ to, label, Icon }) => (
          <Magnetic key={to}>
            <Link to={to} className="tap flex min-h-[88px] flex-col items-center justify-center gap-2 rounded-[12px] border border-[var(--glass-border)] bg-[var(--tile)] px-1 text-center text-xs font-medium transition-all hover:bg-[var(--sel)] hover:shadow-md">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-[#64d2ff] to-[#0a84ff] text-white shadow-[0_6px_16px_rgba(10, 132, 255, 0.5)]"><Icon size={18} /></span>{label}
            </Link>
          </Magnetic>
        ))}
      </div>
    </WidgetCard>
  );
}

/* ---------- 11. Insight (typed summary built from real counts, no AI call) ---------- */
function useTyped(text: string) {
  const reduce = useReducedMotion();
  const [k, setK] = useState(0);
  useEffect(() => {
    if (reduce) return setK(text.length);
    setK(0);
    const id = setInterval(() => setK((v) => (v >= text.length ? (clearInterval(id), v) : v + 1)), 16);
    return () => clearInterval(id);
  }, [text, reduce]);
  return text.slice(0, k);
}

export function Insight({ n, className }: { n: Counts; className: string }) {
  const ready = Object.values(n).every((v) => v !== undefined);
  const issued = (n.open ?? 0) + (n.paid ?? 0);
  const pct = issued ? Math.round(((n.paid ?? 0) / issued) * 100) : 0;
  const text = ready
    ? `${n.active} subscription${n.active === 1 ? " is" : "s are"} active${n.paused ? ` and ${n.paused} paused` : ""}. ${n.open} invoice${n.open === 1 ? " is" : "s are"} open, ${n.overdue} overdue${n.overdue ? ", so follow those up first" : ", nothing is late"}. ${pct}% of issued invoices are collected.`
    : "";
  const typed = useTyped(text);
  return (
    <WidgetCard className={className} title="Summary" info="Written from your live counts. No external AI service is called.">
      <div className="glass shimmer-edge glass-flat relative h-full min-h-[120px] p-4">
        <Sparkles size={16} className="mb-2 text-accent" />
        {ready ? (
          <>
            <span className="sr-only">{text}</span>
            <p aria-hidden className="text-sm leading-relaxed">{typed}<span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-accent align-middle" /></p>
          </>
        ) : (
          <div className="space-y-2"><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-4/5" /><Skeleton className="h-3 w-3/5" /></div>
        )}
      </div>
    </WidgetCard>
  );
}

/* ---------- 12. System status (real /api/healthz) ---------- */
const DOT = { ok: "bg-[#30D158]", warn: "bg-[#FF9F0A]", bad: "bg-[#FF453A]" } as const;
const lvl = (s?: string) => (s === "ok" ? "ok" : s === "disabled" ? "warn" : "bad");
const word = (s?: string) => (s === "ok" ? "Operational" : s === "disabled" ? "Disabled" : s === "down" ? "Down" : "Unknown");

export function SystemStatus({ className }: { className: string }) {
  const h = useQuery({ queryKey: ["health"], queryFn: () => api.get<Health>("/api/healthz"), refetchInterval: 30000, retry: false });
  const rows = [
    { name: "API", s: h.data ? "ok" : h.isError ? "down" : undefined },
    { name: "Database", s: h.data?.app_db ?? (h.isError ? "down" : undefined) },
    { name: "Odoo ledger", s: h.data?.odoo.status ?? (h.isError ? "down" : undefined) },
  ];
  return (
    <WidgetCard className={className} title="System status" info="Live health checks, refreshed every 30 seconds. Odoo shows Disabled when the integration is switched off.">
      {h.isLoading ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-9 w-full" />)}</div> : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.name} className="flex items-center gap-3 rounded-[12px] border border-[var(--glass-border)] bg-[var(--tile)] px-3 py-2.5 text-sm">
              <span className="relative flex h-2.5 w-2.5">
                {lvl(r.s) === "ok" && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${DOT.ok}`} />}
                <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${DOT[lvl(r.s)]}`} />
              </span>
              <span className="flex-1">{r.name}</span>
              <span className="text-xs text-fg2">{word(r.s)}</span>
            </li>
          ))}
        </ul>
      )}
    </WidgetCard>
  );
}

/* ---------- Profile card (the reference's avatar + three numbers tile) ---------- */
export function ProfileCard({ n, className }: { n: Counts; className: string }) {
  const { user } = useAuth();
  if (!user) return null;
  const stats: [string, number | undefined][] = [["Active", n.active], ["Open", n.open], ["Overdue", n.overdue]];
  return (
    <WidgetCard className={className}>
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <span className="grid h-20 w-20 place-items-center rounded-full bg-gradient-to-b from-[#409cff] to-[#0071e3] text-3xl font-semibold text-white shadow-lg">{(user.name || user.email).charAt(0).toUpperCase()}</span>
        <p className="mt-3 text-lg font-semibold">{user.name || user.email.split("@")[0]}</p>
        <p className="max-w-full truncate text-sm text-fg2">{user.email}</p>
        <div className="mt-5 grid w-full grid-cols-3 gap-2">
          {stats.map(([label, v]) => (
            <div key={label}>
              <p className="text-[11px] text-fg2">{label}</p>
              <p className="tabular-nums text-2xl font-semibold">{v ?? "–"}</p>
            </div>
          ))}
        </div>
      </div>
    </WidgetCard>
  );
}
