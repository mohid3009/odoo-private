import { motion } from "framer-motion";
import { useId, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CountUp } from "../ui/glass";

export interface Point { label: string; value: number }
export interface Seg { label: string; value: number; color: string }

const useUid = () => useId().replace(/:/g, "");

export function Sparkline({ data, color = "#0A84FF" }: { data: number[]; color?: string }) {
  const id = useUid();
  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} strokeLinecap="round" fill={`url(#${id})`} dot={false} animationDuration={1000} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Glass tooltip with a coloured marker; Recharts hands us (active, payload, label).
function GlassTip({ active, payload, label, format }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tip px-3 py-2 text-xs">
      <p className="mb-1 text-fg2">{label}</p>
      <p className="flex items-center gap-2 tabular-nums text-sm font-semibold">
        <span className="h-2 w-2 rounded-full bg-[#0A84FF]" />
        {format(payload[0].value)}
      </p>
    </div>
  );
}

// Changing `data` morphs the curve (Recharts tweens between datasets) instead of re-drawing it.
export function TrendChart({ data, format }: { data: Point[]; format: (n: number) => string }) {
  const id = useUid();
  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`${id}f`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0A84FF" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#0A84FF" stopOpacity={0} />
            </linearGradient>
            <linearGradient id={`${id}l`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#0A84FF" />
              <stop offset="100%" stopColor="#64D2FF" />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeDasharray="4 6" />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "var(--muted)", fontSize: 11 }} interval="preserveStartEnd" minTickGap={28} />
          <YAxis hide domain={[0, "auto"]} />
          <Tooltip content={(p) => <GlassTip {...p} format={format} />} cursor={{ stroke: "var(--fg2)", strokeDasharray: "3 4", strokeOpacity: 0.5 }} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={`url(#${id}l)`}
            strokeWidth={2.5}
            strokeLinecap="round"
            fill={`url(#${id}f)`}
            activeDot={{ r: 5, fill: "#0A84FF", stroke: "var(--bg)", strokeWidth: 2 }}
            animationDuration={1000}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Hand-drawn SVG donut: rounded caps + real gaps are trivial here, awkward in a charting lib.
export function Donut({ segments, centerLabel }: { segments: Seg[]; centerLabel: string }) {
  const [hot, setHot] = useState<number | null>(null);
  const R = 74;
  const C = 2 * Math.PI * R;
  const total = segments.reduce((a, s) => a + s.value, 0);
  const drawn = segments.filter((s) => s.value > 0);
  const gap = drawn.length > 1 ? 22 : 0; // > stroke width, so round caps never touch
  let start = 0;
  const arcs = segments.map((s, i) => {
    const full = total ? (s.value / total) * C : 0;
    const a = { s, i, len: Math.max(full - gap, 0), off: -(start + gap / 2) };
    start += full;
    return a;
  });
  const cur = hot === null ? null : segments[hot];
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative h-[200px] w-[200px]">
        <svg viewBox="0 0 200 200" className="h-full w-full" role="img" aria-label={`${centerLabel}: ${total}`}>
          <circle cx="100" cy="100" r={R} fill="none" stroke="var(--grid)" strokeWidth="18" />
          {arcs.filter((a) => a.s.value > 0).map(({ s, i, len, off }) => (
            <motion.circle
              key={s.label}
              cx="100" cy="100" r={R} fill="none" stroke={s.color} strokeLinecap="round"
              transform="rotate(-90 100 100)"
              strokeDashoffset={off}
              initial={{ strokeDasharray: `0 ${C}`, strokeWidth: 18 }}
              animate={{ strokeDasharray: `${len} ${C - len}`, strokeWidth: hot === i ? 25 : 18, opacity: hot === null || hot === i ? 1 : 0.4 }}
              transition={{ duration: 1, ease: "easeOut" }}
              onMouseEnter={() => setHot(i)}
              onMouseLeave={() => setHot(null)}
            />
          ))}
        </svg>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="tabular-nums text-4xl font-semibold tracking-tight"><CountUp value={cur ? cur.value : total} duration={0.5} /></p>
            <p className="text-[11px] text-fg2">{cur ? cur.label : centerLabel}</p>
          </div>
        </div>
      </div>
      <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-fg2">
        {segments.map((s, i) => (
          <li key={s.label}>
            <button className="tap flex items-center gap-1.5 rounded-full px-1.5 py-1 hover:text-fg" onMouseEnter={() => setHot(i)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(i)} onBlur={() => setHot(null)}>
              <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
              {s.label} <span className="tabular-nums text-fg">{s.value}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Gauge({ value, label }: { value: number; label: string }) {
  const id = useUid();
  const R = 62;
  const C = 2 * Math.PI * R;
  const pct = Math.min(Math.max(value, 0), 100);
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-[160px] w-[160px]">
        <svg viewBox="0 0 160 160" className="h-full w-full" role="img" aria-label={`${label}: ${pct}%`}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#30D158" />
              <stop offset="100%" stopColor="#7CEB9B" />
            </linearGradient>
          </defs>
          <circle cx="80" cy="80" r={R} fill="none" stroke="var(--grid)" strokeWidth="14" />
          <motion.circle
            cx="80" cy="80" r={R} fill="none" stroke={`url(#${id})`} strokeWidth="14" strokeLinecap="round"
            transform="rotate(-90 80 80)"
            initial={{ strokeDasharray: `0 ${C}` }}
            animate={{ strokeDasharray: `${(pct / 100) * C} ${C}`, opacity: pct > 0 ? 1 : 0 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <p className="tabular-nums text-4xl font-semibold tracking-tight"><CountUp value={pct} />%</p>
        </div>
      </div>
      <p className="text-center text-xs text-fg2">{label}</p>
    </div>
  );
}

// Custom bars (not Recharts) so each bar can rise with its own stagger and neighbours can dim on hover.
export function BarRise({ data, format }: { data: Point[]; format: (n: number) => string }) {
  const [hot, setHot] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex h-full min-h-[170px] items-stretch gap-2" role="img" aria-label={data.map((d) => `${d.label} ${format(d.value)}`).join(", ")}>
      {data.map((d, i) => (
        <div
          key={d.label}
          tabIndex={0}
          className="flex min-w-0 flex-1 flex-col items-center justify-end gap-1.5 outline-none"
          onMouseEnter={() => setHot(i)} onMouseLeave={() => setHot(null)} onFocus={() => setHot(i)} onBlur={() => setHot(null)}
        >
          <span className={`tabular-nums text-[11px] transition-opacity ${hot === i ? "opacity-100" : "opacity-0"}`}>{format(d.value)}</span>
          <div className="flex w-full flex-1 items-end">
            <motion.div
              className="mx-auto w-full max-w-[28px] rounded-t-[8px]"
              style={{ background: "linear-gradient(to top,rgba(10,132,255,.85),rgba(64,156,255,.6))" }}
              initial={{ height: 0 }}
              animate={{ height: `${(d.value / max) * 100}%`, opacity: hot === null || hot === i ? 1 : 0.35 }}
              transition={{ height: { duration: 0.8, delay: i * 0.06, ease: "easeOut" }, opacity: { duration: 0.2 } }}
            />
          </div>
          <span className="text-[11px] text-muted">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

const STOPS = [[100, 210, 255], [10, 132, 255], [0, 80, 200]]; // sky -> blue -> deep blue
function ramp(v: number) {
  const t = Math.min(Math.max(v, 0), 1);
  const [a, b, u] = t < 0.5 ? [STOPS[0], STOPS[1], t * 2] : [STOPS[1], STOPS[2], (t - 0.5) * 2];
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * u));
  return `rgba(${c.join(",")},${0.18 + 0.82 * t})`;
}

export function Heat({ data, rows, cols }: { data: number[][]; rows: string[]; cols: string[] }) {
  return (
    <div>
      <div className="grid items-center gap-1" style={{ gridTemplateColumns: `auto repeat(${cols.length}, minmax(0, 1fr))` }}>
        <span />
        {cols.map((c, i) => <span key={i} className="text-center text-[10px] text-muted">{i % 2 === 0 ? c : ""}</span>)}
        {rows.map((r, ri) => (
          <div key={r} className="contents">
            <span className="pr-2 text-[11px] text-muted">{r}</span>
            {data[ri].map((v, ci) => (
              <motion.span
                key={ci}
                title={`${r} ${cols[ci]} · ${Math.round(v * 100)}% of peak`}
                className="h-6 rounded-md"
                style={{ background: ramp(v) }}
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, delay: (ri + ci) * 0.03, ease: "easeOut" }}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 text-[10px] text-muted">
        quiet
        <span className="h-1.5 flex-1 rounded-full" style={{ background: `linear-gradient(90deg,${ramp(0)},${ramp(0.5)},${ramp(1)})` }} />
        busy
      </div>
    </div>
  );
}
