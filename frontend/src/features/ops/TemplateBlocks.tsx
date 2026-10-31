import { useState, type DragEvent, type HTMLAttributes } from "react";

// Scratch-style message editor: the template is a row of blocks, plain text you type and pill-shaped {placeholders} you drag.
// It reads and writes the same `{name}` string the backend renders (notifications.services.notify), nothing else changes.
const VARS: Record<string, { label: string; sample: string; bg: string }> = {
  customer_name: { label: "Customer name", sample: "Asha", bg: "linear-gradient(135deg,#4ade80,#16a34a)" },
  invoice_number: { label: "Invoice no.", sample: "INV-000012", bg: "linear-gradient(135deg,#60a5fa,#2563eb)" },
  subscription_number: { label: "Subscription no.", sample: "SUB-000003", bg: "linear-gradient(135deg,#a78bfa,#7c3aed)" },
  amount: { label: "Amount (₹)", sample: "4694.04", bg: "linear-gradient(135deg,#fbbf24,#d97706)" },
  due_date: { label: "Due date", sample: "2026-11-15", bg: "linear-gradient(135deg,#fb7185,#e11d48)" },
  expiry_date: { label: "Expiry date", sample: "2027-01-31", bg: "linear-gradient(135deg,#f472b6,#be185d)" },
  link: { label: "Link", sample: "https://app.example.com/portal/invoices/12", bg: "linear-gradient(135deg,#2dd4bf,#0f766e)" },
  balance_note: { label: "Balance note", sample: "Remaining balance: ₹2,000.00.", bg: "linear-gradient(135deg,#94a3b8,#475569)" },
};
const FALLBACK_BG = "linear-gradient(135deg,#94a3b8,#475569)";

type Tok = { k: "t" | "v"; v: string };

// Always text, pill, text, pill, …, text: a text box sits at every gap so you can type between pills.
function norm(toks: Tok[]): Tok[] {
  const out: Tok[] = [];
  for (const t of toks) {
    const last = out[out.length - 1];
    if (t.k === "t") {
      if (last?.k === "t") last.v += t.v;
      else out.push({ ...t });
    } else {
      if (last?.k !== "t") out.push({ k: "t", v: "" });
      out.push(t);
    }
  }
  if (out[out.length - 1]?.k !== "t") out.push({ k: "t", v: "" });
  return out;
}
const parse = (s: string): Tok[] =>
  norm(s.split(/(\{\w+\})/).map((p) => { const m = p.match(/^\{(\w+)\}$/); return m ? { k: "v" as const, v: m[1] } : { k: "t" as const, v: p }; }));
const serialize = (toks: Tok[]) => toks.map((t) => (t.k === "v" ? `{${t.v}}` : t.v)).join("");
const preview = (s: string) => s.replace(/\{(\w+)\}/g, (_, n) => VARS[n]?.sample ?? "");

function Pill({ name, onRemove, ...drag }: { name: string; onRemove?: () => void } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span {...drag} draggable className="inline-flex cursor-grab select-none items-center gap-1 rounded-full py-1 pl-3 pr-3 text-xs font-semibold text-white shadow-md active:cursor-grabbing" style={{ background: VARS[name]?.bg ?? FALLBACK_BG }} title={`{${name}}`}>
      {VARS[name]?.label ?? name}
      {onRemove && <button type="button" aria-label={`Remove ${VARS[name]?.label ?? name}`} onClick={onRemove} className="-mr-1 grid h-4 w-4 place-items-center rounded-full bg-white/25 text-[10px] leading-none hover:bg-white/45">×</button>}
    </span>
  );
}

export default function TemplateBlocks({ body, onSave }: { body: string; onSave: (b: string) => void }) {
  const [toks, setToks] = useState<Tok[]>(() => parse(body));
  const [over, setOver] = useState<{ i: number; after: boolean } | null>(null);
  const text = serialize(toks);

  // Drop payload: { name } from the palette, or { name, from } when moving a pill that is already in the message.
  const place = (e: DragEvent, at: number) => {
    e.preventDefault();
    e.stopPropagation();
    setOver(null);
    let p: { name: string; from?: number };
    try { p = JSON.parse(e.dataTransfer.getData("text/plain")); } catch { return; }
    if (!p?.name) return;
    const next = toks.slice();
    let pos = at;
    if (p.from !== undefined) { next.splice(p.from, 1); if (p.from < at) pos -= 1; }
    next.splice(pos, 0, { k: "v", v: p.name });
    setToks(norm(next));
  };
  const hover = (e: DragEvent, i: number) => {
    e.preventDefault();
    e.stopPropagation();
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setOver({ i, after: e.clientX > r.left + r.width / 2 });
  };
  const start = (e: DragEvent, name: string, from?: number) => {
    e.dataTransfer.setData("text/plain", JSON.stringify({ name, from }));
    e.dataTransfer.effectAllowed = from === undefined ? "copy" : "move";
  };
  const append = (name: string) => setToks((t) => norm([...t, { k: "v", v: name }]));
  const edit = (i: number, v: string) => setToks((t) => t.map((x, j) => (j === i ? { ...x, v } : x)));
  const remove = (i: number) => setToks((t) => norm(t.filter((_, j) => j !== i)));

  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-1.5" aria-label="Available placeholders">
        <span className="mr-1 text-xs text-slate-500">Drag into the message (or click):</span>
        {Object.keys(VARS).map((n) => (
          <span key={n} onClick={() => append(n)}><Pill name={n} onDragStart={(e) => start(e, n)} /></span>
        ))}
      </div>

      <div
        role="group" aria-label="Message template"
        onDragOver={(e) => { e.preventDefault(); setOver({ i: toks.length - 1, after: true }); }}
        onDragLeave={() => setOver(null)}
        onDrop={(e) => place(e, toks.length)}
        className="flex min-h-[56px] flex-wrap items-center gap-y-2 rounded-2xl border-2 border-dashed border-[rgba(0, 113, 227, 0.35)] bg-[rgba(0, 113, 227, 0.05)] p-3"
      >
        {toks.map((t, i) => {
          const mark = over?.i === i ? (over.after ? "shadow-[inset_-3px_0_0_#0a84ff]" : "shadow-[inset_3px_0_0_#0a84ff]") : "";
          return (
            <span key={i} className={`inline-flex rounded ${mark}`} onDragOver={(e) => hover(e, i)} onDrop={(e) => {
              const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
              place(e, e.clientX > r.left + r.width / 2 ? i + 1 : i);
            }}>
              {t.k === "t" ? (
                <input aria-label="Text" value={t.v} onChange={(e) => edit(i, e.target.value)} onDrop={(e) => e.preventDefault()}
                  className="min-w-[1.5rem] bg-transparent px-1 py-1 outline-none focus-visible:!shadow-none" style={{ width: `${Math.max(t.v.length, 1) + 1}ch`, maxWidth: "100%" }} />
              ) : (
                <Pill name={t.v} onDragStart={(e) => start(e, t.v, i)} onRemove={() => remove(i)} />
              )}
            </span>
          );
        })}
      </div>

      <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600"><span className="font-medium">Preview:</span> {preview(text) || "(empty)"}</p>
      <div className="flex gap-2">
        <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={text === body || !text.trim()} onClick={() => onSave(text)}>Save template</button>
        <button className="rounded border px-3 py-1 disabled:opacity-40" disabled={text === body} onClick={() => setToks(parse(body))}>Reset</button>
      </div>
    </div>
  );
}
