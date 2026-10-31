import { useQueries } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Repeat, Wallet } from "lucide-react";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { Segmented, STAGGER } from "../../components/ui/glass";
import { useRange, type Range } from "../../lib/theme";
import {
  ActivityFeed, CollectionGauge, Insight, InvoicesBars, InvoicesTable, Kpi, PaymentHeat, ProfileCard, QuickActions, StatusDonut, SystemStatus,
  TrendWidget, type Counts,
} from "./widgets";

const RANGES: { value: Range; label: string }[] = [{ value: 7, label: "7d" }, { value: 30, label: "30d" }, { value: 90, label: "90d" }];

// One cheap count query per tile; the API already scopes every list to the caller (customers see only their own).
const COUNTS = {
  active: "/api/subscriptions/?status=active",
  paused: "/api/subscriptions/?status=paused",
  pending: "/api/subscriptions/?status=quotation",
  open: "/api/invoices/?status=confirmed",
  overdue: "/api/invoices/?overdue=true",
  paid: "/api/invoices/?status=paid",
} as const;
const KEYS = Object.keys(COUNTS) as (keyof Counts)[];

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1 });

export default function Home() {
  const { user } = useAuth();
  const { range, setRange, endDate, setEndDate } = useRange();
  const results = useQueries({
    queries: KEYS.map((k) => ({ queryKey: ["home", k], queryFn: () => api.get<Page<unknown>>(`${COUNTS[k]}&page_size=1`) })),
  });
  if (!user) return null;
  const staff = user.role !== "customer";
  const n = Object.fromEntries(KEYS.map((k, i) => [k, results[i].data?.count])) as Counts;
  // The header shows the window the widgets cover: `range` days ending on the picked date (default today).
  const todayIso = new Date().toLocaleDateString("en-CA");
  const end = new Date(`${endDate || todayIso}T00:00:00`);
  const start = new Date(end);
  start.setDate(end.getDate() - (range - 1));
  const fmt = (d: Date, year = false) => d.toLocaleDateString("en-IN", { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}) });
  const label = `${fmt(start)} – ${fmt(end, true)}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-fg2" aria-live="polite">{label}{endDate ? "" : " · up to today"}</p>
          <h2 className="text-lg font-medium tracking-tight">{staff ? "Billing overview" : "My account"}</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted">Range</span>
          <Segmented id="range-seg" options={RANGES} value={range} onChange={setRange} />
          <label className="ml-2 flex items-center gap-1.5 text-[11px] text-muted">
            Ending
            <input
              type="date" aria-label="Range end date" max={todayIso} value={endDate || todayIso}
              onChange={(e) => setEndDate(!e.target.value || e.target.value >= todayIso ? "" : e.target.value)}
              className="rounded-full border border-[var(--glass-border)] bg-[var(--glass)] px-3 py-1 text-xs text-fg outline-none [color-scheme:light]"
            />
          </label>
          {endDate && <button onClick={() => setEndDate("")} className="rounded-full bg-[var(--sel)] px-3 py-1 text-xs font-medium hover:bg-[var(--tile)]">Today</button>}
        </div>
      </div>

      <motion.div variants={STAGGER} initial="hidden" animate="show" className="dark-scope grid grid-cols-1 gap-5 text-fg md:grid-cols-6 xl:grid-cols-12">
        {/* Row 1: four KPI tiles, the last one filled (as in the reference) */}
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={Repeat} label="Active subscriptions" value={n.active} delta={4.2} seed={1} color="#30d158" info="Subscriptions currently billing." />
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={Wallet} label="Open invoices" value={n.open} delta={-2.1} seed={2} color="#0a84ff" info="Issued invoices that are not fully paid yet." />
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={AlertTriangle} label="Overdue" value={n.overdue} delta={-8.4} seed={3} color="#ff9f0a" info="Open invoices past their due date. Lower is better." />
        <Kpi highlight className="md:col-span-3 xl:col-span-3" Icon={CheckCircle2} label="MRR · sample" value={184250} format={(v) => inr.format(v)} delta={6.8} seed={4} color="#0071e3" info="Monthly recurring revenue (sample figure until the finance API lands)." />

        {/* Row 2: wide trend, gauge, profile */}
        <TrendWidget className="md:col-span-6 xl:col-span-6" />
        <CollectionGauge n={n} className="md:col-span-3 xl:col-span-3" />
        <ProfileCard n={n} className="md:col-span-3 xl:col-span-3" />

        {/* Row 3: invoices, activity, quick actions */}
        <InvoicesTable className="md:col-span-6 xl:col-span-6" />
        <ActivityFeed className="md:col-span-3 xl:col-span-3" />
        <QuickActions className="md:col-span-3 xl:col-span-3" />

        {/* Row 4: breakdowns */}
        <StatusDonut n={n} className="md:col-span-3 xl:col-span-4" />
        <InvoicesBars className="md:col-span-3 xl:col-span-4" />
        <PaymentHeat className="md:col-span-6 xl:col-span-4" />

        <Insight n={n} className="md:col-span-3 xl:col-span-6" />
        <SystemStatus className="md:col-span-3 xl:col-span-6" />
      </motion.div>

      <p className="text-xs text-muted">Counts, the table and system status are live. Trend lines, deltas, MRR, weekly bars, the heatmap and the activity feed are sample data.</p>
    </div>
  );
}
