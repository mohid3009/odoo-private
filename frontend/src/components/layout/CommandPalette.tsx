import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Search, type LucideIcon } from "lucide-react";

export interface Cmd { label: string; Icon: LucideIcon; run: () => void }

export default function CommandPalette({ open, onClose, items }: { open: boolean; onClose: () => void; items: Cmd[] }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const list = useMemo(() => items.filter((c) => c.label.toLowerCase().includes(q.toLowerCase())), [items, q]);
  useEffect(() => { if (open) { setQ(""); setI(0); } }, [open]);
  useEffect(() => setI(0), [q]);

  const go = (c?: Cmd) => { if (c) { onClose(); c.run(); } };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); setI((n) => Math.min(n + 1, list.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setI((n) => Math.max(n - 1, 0)); }
    else if (e.key === "Enter") go(list[i]);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="no-print fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[14vh]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onMouseDown={onClose}
        >
          <motion.div
            role="dialog" aria-modal="true" aria-label="Command palette"
            className="glass glass-flat w-full max-w-lg overflow-hidden"
            initial={{ y: -12, scale: 0.97, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: -8, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-[var(--glass-border)] px-5">
              <Search size={18} className="text-muted" />
              <input
                autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
                role="combobox" aria-expanded="true" aria-controls="cmd-list"
                placeholder="Search pages and actions…"
                className="w-full bg-transparent px-2 py-5 text-base outline-none placeholder:text-muted focus-visible:!shadow-none"
              />
              <kbd className="rounded-md border border-[var(--glass-border)] px-1.5 py-0.5 text-[10px] text-muted">Esc</kbd>
            </div>
            <ul id="cmd-list" role="listbox" className="max-h-80 overflow-auto p-2">
              {list.map((c, n) => (
                <li key={c.label} role="option" aria-selected={n === i}>
                  <button
                    onMouseEnter={() => setI(n)} onClick={() => go(c)}
                    className={`tap flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${n === i ? "bg-[var(--sel)] text-fg" : "text-fg2"}`}
                  >
                    <c.Icon size={17} className={n === i ? "text-accent" : ""} />
                    {c.label}
                  </button>
                </li>
              ))}
              {list.length === 0 && <li className="px-3 py-6 text-center text-sm text-fg2">Nothing matches “{q}”.</li>}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
