import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Point } from "../components/charts/charts";

// Sample data for widgets whose API doesn't exist yet. Deterministic (seeded) so screenshots are stable.
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function series(n: number, base: number, vol: number, seed: number, drift = 0): number[] {
  const r = rng(seed);
  let v = base;
  return Array.from({ length: n }, () => {
    v = Math.max(base * 0.3, v + (r() - 0.5) * vol + drift);
    return Math.round(v);
  });
}

/**
 * Swap point: replace `factory` with `() => api.get(...)` to go live. `keepPreviousData` keeps the old
 * dataset on screen while the new one loads, so charts morph instead of flashing a skeleton.
 */
export function useMock<T>(key: unknown[], factory: () => T, delay = 500) {
  return useQuery({
    queryKey: ["mock", ...key],
    queryFn: () => new Promise<T>((res) => setTimeout(() => res(factory()), delay)),
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
}

export type Period = "Day" | "Week" | "Month" | "Year";
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// The picked end date changes the sample data too: daySalt turns it into a small number mixed into each seed.
export const daySalt = (d: string) => (d ? Number(d.replace(/-/g, "")) % 997 : 0);

export function trend(period: Period, range: number, salt = 0): Point[] {
  const n = period === "Day" ? 24 : period === "Week" ? 7 : period === "Month" ? range : 12;
  const labels = (i: number) =>
    period === "Day" ? `${String(i).padStart(2, "0")}:00` : period === "Week" ? DAYS[i] : period === "Month" ? `${i + 1}` : MONTHS[i];
  return series(n, 48000, 14000, n * 7 + range + salt, 700).map((value, i) => ({ label: labels(i), value }));
}

export const spark = (seed: number) => series(14, 50, 14, seed, 1);

export function bars(range: number, salt = 0): Point[] {
  return series(8, 60, 30, range + 3 + salt).map((value, i) => ({ label: `W${i + 1}`, value }));
}

export const HEAT_ROWS = DAYS;
export const HEAT_COLS = ["0", "2", "4", "6", "8", "10", "12", "14", "16", "18", "20", "22"];
export function heat(range: number, salt = 0): number[][] {
  const r = rng(range * 13 + salt);
  return DAYS.map(() => HEAT_COLS.map((_, c) => Math.min(1, (c >= 4 && c <= 8 ? 0.55 : 0.12) + r() * 0.5)));
}

export type ActivityKind = "payment" | "invoice" | "renewal" | "failed";
export interface Activity { id: number; kind: ActivityKind; text: string; at: number }

const POOL: Pick<Activity, "kind" | "text">[] = [
  { kind: "payment", text: "Payment received for INV-0042" },
  { kind: "invoice", text: "Invoice generated for Acme Studio" },
  { kind: "renewal", text: "Subscription renewed · Pro plan" },
  { kind: "failed", text: "Card declined, retry scheduled" },
  { kind: "payment", text: "UPI payment confirmed" },
  { kind: "invoice", text: "Reminder sent for overdue invoice" },
];
let seq = 100;
export const nextActivity = (): Activity => ({ id: seq++, ...POOL[seq % POOL.length], at: Date.now() });
export const activitySeed = (): Activity[] =>
  POOL.map((p, i) => ({ id: i, ...p, at: Date.now() - (i + 1) * 17 * 60_000 }));
