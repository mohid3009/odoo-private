import { useQueries, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, Repeat, Wallet, Banknote } from "lucide-react";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import { useAuth } from "../../auth/AuthProvider";
import { STAGGER } from "../../components/ui/glass";
import {
  ActivityFeed, CollectionGauge, Insight, InvoicesBars, InvoicesTable, Kpi, ProfileCard, QuickActions, StatusDonut, SystemStatus,
  TrendWidget, type Counts, type Summary,
} from "./widgets";

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
  const results = useQueries({
    queries: KEYS.map((k) => ({ queryKey: ["home", k], queryFn: () => api.get<Page<unknown>>(`${COUNTS[k]}&page_size=1`) })),
  });
  const summary = useQuery({ queryKey: ["home", "summary"], queryFn: () => api.get<Summary>("/api/dashboard/summary/") });
  if (!user) return null;
  const staff = user.role !== "customer";
  const n = Object.fromEntries(KEYS.map((k, i) => [k, results[i].data?.count])) as Counts;
  const k = summary.data?.kpis;
  const money = (s?: string) => (s === undefined ? undefined : Number(s)); // display only, the API sends exact strings

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-medium tracking-tight">{staff ? "Billing overview" : "My account"}</h2>

      <motion.div variants={STAGGER} initial="hidden" animate="show" className="dark-scope grid grid-cols-1 gap-5 text-fg md:grid-cols-6 xl:grid-cols-12">
        {/* Row 1: four KPI tiles */}
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={Repeat} label="Active subscriptions" value={n.active} color="#30d158" info="Subscriptions currently billing." />
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={Wallet} label="Outstanding" value={money(k?.outstanding)} format={(v) => inr.format(v)} sub={n.open === undefined ? undefined : `${n.open} open`} color="#0a84ff" info="Amount still owed on issued invoices." />
        <Kpi className="md:col-span-3 xl:col-span-3" Icon={AlertTriangle} label="Overdue" value={k?.overdue_count} sub={k ? inr.format(Number(k.overdue_amount)) : undefined} color="#ff9f0a" info="Open invoices past their due date, and the amount they hold. Lower is better." />
        <Kpi highlight className="md:col-span-3 xl:col-span-3" Icon={Banknote} label="Revenue collected" value={money(k?.revenue_collected)} format={(v) => inr.format(v)} color="#0071e3" info="Completed payments received, all time." />

        {/* Row 2: wide trend, gauge, profile */}
        <TrendWidget q={summary} className="md:col-span-6 xl:col-span-6" />
        <CollectionGauge n={n} className="md:col-span-3 xl:col-span-3" />
        <ProfileCard n={n} className="md:col-span-3 xl:col-span-3" />

        {/* Row 3: invoices, activity, quick actions */}
        <InvoicesTable className="md:col-span-6 xl:col-span-6" />
        <ActivityFeed q={summary} className="md:col-span-3 xl:col-span-3" />
        <QuickActions className="md:col-span-3 xl:col-span-3" />

        {/* Row 4: breakdowns */}
        <StatusDonut n={n} className="md:col-span-3 xl:col-span-4" />
        <InvoicesBars q={summary} className="md:col-span-3 xl:col-span-8" />

        <Insight n={n} className="md:col-span-3 xl:col-span-6" />
        <SystemStatus className="md:col-span-3 xl:col-span-6" />
      </motion.div>
    </div>
  );
}
