import React, { useState } from "react";
import { Link } from "react-router-dom";
import Hero40 from "@/components/originkit/hero-40";
import { useQuery } from "@tanstack/react-query";
import { api, Health } from "../api/client";

export default function BrightloopIntro() {
  const [showSystemHealth, setShowSystemHealth] = useState(false);

  // Background health query for Odoo/App DB status
  const { data: healthData } = useQuery({
    queryKey: ["healthz"],
    queryFn: () => api.get<Health>("/api/healthz").catch(() => null),
    retry: false,
    staleTime: 30000,
  });

  return (
    <div className="min-h-screen w-full bg-[#0B0B0D] text-[#C8C8D0] flex flex-col items-center justify-start overflow-x-hidden selection:bg-white/20 selection:text-white">
      {/* Optional diagnostic bar for Odoo backend */}
      {healthData && (
        <aside
          aria-label="System diagnostic bar"
          className="w-full bg-[#0E0E12] border-b border-white/[0.08] px-6 py-2 text-xs text-[#9A9AA3] flex items-center justify-between z-50 sticky top-0"
        >
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Odoo Sync: <strong className="text-white">{healthData.odoo?.status || "Ready"}</strong></span>
            </span>
            <span className="hidden sm:inline text-white/[0.15]">|</span>
            <span className="hidden sm:inline">Database: <strong className="text-white">{healthData.app_db}</strong></span>
          </div>
          <Link to="/login" className="text-xs text-white hover:underline">
            Go to Billing Console →
          </Link>
        </aside>
      )}

      {/* Fullscreen 100vw x 100vh Hero with Dither & Human Hand Hover Reveal */}
      <div className="w-full h-screen overflow-hidden">
        <Hero40 />
      </div>

      {/* -------------------- PITCH-DECK SECTIONS BELOW HERO -------------------- */}
      <div className="w-full max-w-[1440px] px-4 sm:px-8 lg:px-12 py-20">
        
        {/* SECTION 1: THE PROBLEM */}
        <section
          id="problem"
          className="rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/80 p-8 sm:p-14 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] relative overflow-hidden"
        >
          <div className="max-w-4xl mb-14">
            <span className="text-[11px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-4">
              01 / THE BREAKDOWN
            </span>
            <h2 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-[-0.03em] leading-tight text-white">
              Spreadsheets. Missed renewals. Wrong invoices. Payments matched by hand.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            {[
              {
                num: "01",
                title: "Manual Spreadsheets",
                desc: "Fragmented customer sheets quickly drift out of sync, leading to silent customer churn and hidden revenue leakage.",
              },
              {
                num: "02",
                title: "Missed Renewals",
                desc: "Contracts expire or auto-renew with outdated pricing because no automated system alerts the team in advance.",
              },
              {
                num: "03",
                title: "Invoicing Errors",
                desc: "Proration math, tiered charges, and tax discrepancies trigger customer billing disputes and chargebacks.",
              },
              {
                num: "04",
                title: "Manual Reconciliation",
                desc: "Finance teams waste hours manually matching bank payments and wire transfers against disconnected invoice numbers.",
              },
            ].map((item) => (
              <div
                key={item.num}
                className="p-6 rounded-2xl border border-white/[0.08] bg-[#121218]/80 hover:border-white/[0.2] transition-colors"
              >
                <div className="text-[12px] font-mono text-[#8A8A94] mb-3">{item.num}</div>
                <h3 className="text-lg font-semibold text-white mb-2 tracking-tight">{item.title}</h3>
                <p className="text-sm text-[#9A9AA3] leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 2: THE SOLUTION */}
        <section
          id="solution"
          className="mt-8 rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/80 p-8 sm:p-14 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] relative overflow-hidden"
        >
          <div className="max-w-3xl mb-16">
            <span className="text-[11px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-4">
              02 / THE ARCHITECTURE
            </span>
            <p className="text-2xl sm:text-4xl lg:text-5xl font-semibold tracking-[-0.03em] text-white leading-tight">
              One connected billing lifecycle that turns complex recurring contracts into reliable, automated cash flow.
            </p>
          </div>

          {/* Visual Flow: Plan -> Subscription -> Invoice -> Payment -> Dashboard */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 relative">
            {[
              {
                step: "01",
                label: "Plan",
                detail: "Define pricing models, intervals, taxes and discount rules.",
              },
              {
                step: "02",
                label: "Subscription",
                detail: "Automated recurring schedules, proration and lifecycle state machines.",
              },
              {
                step: "03",
                label: "Invoice",
                detail: "Zero-touch invoice generation synced directly with Odoo ledger.",
              },
              {
                step: "04",
                label: "Payment",
                detail: "Payment recording, status tracking and automated settlement checks.",
              },
              {
                step: "05",
                label: "Dashboard",
                detail: "Real-time ARR, MRR, overdue exposure and renewal metrics.",
              },
            ].map((node, i, arr) => (
              <div
                key={node.step}
                className="relative p-6 rounded-2xl border border-white/[0.08] bg-[#121218]/90 flex flex-col justify-between group hover:border-white/[0.25] transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-mono text-[#8A8A94]">{node.step}</span>
                    {i < arr.length - 1 && (
                      <span className="text-[#8A8A94] group-hover:text-white transition-colors text-xs font-sans">
                        →
                      </span>
                    )}
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">{node.label}</h3>
                  <p className="text-xs text-[#9A9AA3] leading-relaxed">{node.detail}</p>
                </div>
                <div className="mt-6 w-full h-[1px] bg-white/[0.06] group-hover:bg-white/[0.2] transition-colors" />
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 3: KEY FEATURES */}
        <section
          id="features"
          className="mt-8 rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/80 p-8 sm:p-14 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] relative overflow-hidden"
        >
          <div className="max-w-2xl mb-16">
            <span className="text-[11px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-4">
              03 / CAPABILITIES
            </span>
            <h2 className="text-3xl sm:text-5xl font-bold tracking-[-0.03em] text-white">
              Every detail engineered for subscription scale.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                title: "Plans and variants",
                desc: "Flexible intervals (monthly, quarterly, annual), tier-based pricing, and configurable product add-on variants.",
              },
              {
                title: "Quotation to subscription",
                desc: "Transform signed sales quotes into live, recurring customer contracts in one seamless click.",
              },
              {
                title: "Automatic invoicing",
                desc: "Never miss a billing cycle. Invoices are generated, validated, and sent right on schedule with full Odoo synchronization.",
              },
              {
                title: "Smart discounts",
                desc: "Configure fixed, percentage, or duration-bound promotional discounts with automatic expiration rules.",
              },
              {
                title: "Payment tracking",
                desc: "Live visibility into paid, pending, and overdue invoices with automated reconciliation against bank records.",
              },
              {
                title: "Finance dashboard",
                desc: "Instant executive overview of ARR, MRR, collection rates, and renewal pipeline metrics in under two seconds.",
              },
            ].map((feat) => (
              <div
                key={feat.title}
                className="p-7 rounded-2xl border border-white/[0.08] bg-[#121218]/90 hover:border-white/[0.22] transition-colors"
              >
                <div className="w-2 h-2 rounded-full bg-white mb-4 shadow-[0_0_8px_rgba(255,255,255,0.6)]" />
                <h3 className="text-lg font-semibold text-white mb-2.5 tracking-tight">{feat.title}</h3>
                <p className="text-sm text-[#9A9AA3] leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 4: WHO IT'S FOR */}
        <section
          id="roles"
          className="mt-8 rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/80 p-8 sm:p-14 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] relative overflow-hidden"
        >
          <div className="max-w-2xl mb-16">
            <span className="text-[11px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-4">
              04 / ROLES
            </span>
            <h2 className="text-3xl sm:text-5xl font-bold tracking-[-0.03em] text-white">
              Purpose-built views for every stakeholder.
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                role: "Admin",
                headline: "Total system architecture and control.",
                desc: "Full governance over billing plans, tax matrices, staff permissions, audit logs, and automated cron schedules.",
              },
              {
                role: "Staff",
                headline: "Speed and certainty in daily operations.",
                desc: "Create subscriptions from sales quotes, adjust line items, handle manual payment entries, and answer customer billing inquiries.",
              },
              {
                role: "Customer",
                headline: "Frictionless self-service portal.",
                desc: "Review active subscriptions, download official tax invoices, and monitor renewal dates with zero support tickets.",
              },
            ].map((col) => (
              <div
                key={col.role}
                className="p-8 rounded-2xl border border-white/[0.08] bg-[#121218]/90 flex flex-col justify-between"
              >
                <div>
                  <span className="text-xs font-mono tracking-widest uppercase text-[#9A9AA3] block mb-3">
                    WORKSPACE / {col.role}
                  </span>
                  <h3 className="text-xl font-bold text-white mb-3 tracking-tight">{col.headline}</h3>
                  <p className="text-sm text-[#9A9AA3] leading-relaxed">{col.desc}</p>
                </div>
                <div className="mt-8 text-xs font-mono text-[#8A8A94] border-t border-white/[0.06] pt-4">
                  Brightloop · {col.role} View
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 5: IMPACT NUMBERS */}
        <section
          id="impact"
          className="mt-8 rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/80 p-8 sm:p-14 lg:p-16 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] relative overflow-hidden"
        >
          <div className="max-w-xl mb-16">
            <span className="text-[11px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-4">
              05 / SCALE
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-[-0.03em] text-white">
              Proven accuracy in recurring operations.
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 sm:gap-12">
            {[
              {
                value: "1,248",
                label: "Active subscriptions",
                note: "Managed across monthly and annual cycles",
              },
              {
                value: "100%",
                label: "Invoices created automatically",
                note: "Zero missed deadlines or manual spreadsheets",
              },
              {
                value: "< 2s",
                label: "Dashboard load",
                note: "Instant visibility on recurring financial metrics",
              },
            ].map((stat) => (
              <div key={stat.label} className="border-l border-white/[0.12] pl-6 sm:pl-8">
                <div className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-[-0.04em] text-white mb-3 font-sans">
                  {stat.value}
                </div>
                <div className="text-base font-semibold text-[#E4E4EB] mb-1">{stat.label}</div>
                <div className="text-xs text-[#8A8A94]">{stat.note}</div>
              </div>
            ))}
          </div>
        </section>

        {/* SECTION 6: FINAL BAND */}
        <section className="mt-8 rounded-[24px] border border-white/[0.08] bg-[#0E0E12]/90 p-12 sm:p-20 lg:p-24 text-center flex flex-col items-center justify-center relative overflow-hidden shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)]">
          <span className="text-[11px] sm:text-[12px] tracking-[0.25em] uppercase text-[#9A9AA3] font-medium block mb-5">
            GET STARTED
          </span>
          <h2 className="text-3xl sm:text-5xl lg:text-6xl font-bold tracking-[-0.04em] text-white max-w-2xl mb-8 leading-tight">
            Know your recurring revenue today.
          </h2>

          <Link
            to="/login"
            className="group relative inline-flex items-center gap-2.5 px-8 sm:px-9 py-4 rounded-full bg-gradient-to-r from-white via-[#F4F4F6] to-[#E2E2E8] text-[#0B0B0D] font-semibold text-base shadow-[0_0_28px_rgba(255,255,255,0.22)] hover:shadow-[0_0_40px_rgba(255,255,255,0.5)] transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-white"
          >
            <span>Log in</span>
            <span className="inline-block transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
              ↗
            </span>
          </Link>

          <div className="mt-16 pt-8 w-full border-t border-white/[0.05] flex flex-col sm:flex-row items-center justify-between text-[12px] text-[#8A8A94] gap-4">
            <div>© {new Date().getFullYear()} Brightloop Inc. All rights reserved.</div>
            <div className="flex items-center gap-6">
              <span>Subscription Engine</span>
              <span>Odoo Synchronized</span>
              <span>Near-Zero Churn</span>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
