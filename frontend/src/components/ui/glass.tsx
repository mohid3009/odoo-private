import { animate, AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createContext, HTMLAttributes, MouseEvent, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, Inbox, Info, type LucideIcon } from "lucide-react";

export const EASE = [0.22, 1, 0.36, 1] as const;

// Parent grid uses STAGGER; every WidgetCard inherits ENTER (fade + rise), its body also de-blurs.
// Blur is applied to the body, never the glass itself: a filtered ancestor would break backdrop-filter.
export const STAGGER = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const ENTER = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } } };
const SHARP = { hidden: { filter: "blur(6px)" }, show: { filter: "blur(0px)", transition: { duration: 0.6, ease: EASE } } };

export function Glass({ flat, className = "", ...rest }: HTMLAttributes<HTMLDivElement> & { flat?: boolean }) {
  // spotlight: CSS reads --mx/--my (see .glass::after)
  const move = flat
    ? undefined
    : (e: MouseEvent<HTMLDivElement>) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
      };
  return <div {...rest} onMouseMove={move} className={`glass ${flat ? "glass-flat" : ""} ${className}`} />;
}

// One header pattern for every widget: title (+ info tooltip) left, controls right.
export function WidgetCard({ title, info, controls, className = "", layoutId, children }: {
  title?: string; info?: string; controls?: ReactNode; className?: string; layoutId?: string; children: ReactNode;
}) {
  return (
    <motion.div variants={ENTER} layoutId={layoutId} className={className}>
      <Glass className="flex h-full flex-col p-5 sm:p-6">
        {title && (
          <header className="mb-4 flex min-h-[32px] flex-wrap items-center justify-between gap-x-3 gap-y-2">
            <h2 className="flex items-center gap-1.5 text-[13px] font-semibold text-fg2">
              {title}
              {info && <InfoTip text={info} />}
            </h2>
            {controls}
          </header>
        )}
        <motion.div variants={SHARP} className="min-h-0 flex-1">{children}</motion.div>
      </Glass>
    </motion.div>
  );
}

export function CountUp({ value, format = (n) => Math.round(n).toLocaleString("en-IN"), duration = 1.2 }: {
  value: number; format?: (n: number) => string; duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(0);
  const reduce = useReducedMotion();
  useEffect(() => {
    const c = animate(prev.current, value, {
      duration: reduce ? 0 : duration,
      ease: "easeOut",
      onUpdate: (v) => { if (ref.current) ref.current.textContent = format(v); },
    });
    prev.current = value;
    return () => c.stop();
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={ref}>{format(0)}</span>;
}

// Sliding highlight via shared layout animation; `id` must be unique per control on screen.
export function Segmented<T extends string | number>({ id, options, value, onChange }: {
  id: string; options: { value: T; label: string }[]; value: T; onChange: (v: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex rounded-full bg-[var(--sel)] p-0.5">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={String(o.value)}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(o.value)}
            className={`tap relative rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${on ? "text-fg" : "text-fg2 hover:text-fg"}`}
          >
            {on && (
              <motion.span
                layoutId={id}
                className="absolute inset-0 rounded-full bg-[var(--seg-thumb)] shadow-sm"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export const Skeleton = ({ className = "" }: { className?: string }) => <div className={`skeleton ${className}`} aria-hidden />;

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label={text} className="grid h-5 w-5 place-items-center rounded-full text-muted hover:text-fg">
        <Info size={13} />
      </button>
      <span
        role="tooltip"
        className="tip pointer-events-none absolute left-1/2 top-full z-30 mt-1 w-56 -translate-x-1/2 px-3 py-2 text-xs normal-case tracking-normal opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {text}
      </span>
    </span>
  );
}

export function Empty({ Icon = Inbox, text, action }: { Icon?: LucideIcon; text: string; action?: ReactNode }) {
  return (
    <div className="grid h-full min-h-[120px] place-items-center text-center">
      <div className="space-y-2">
        <span className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-[var(--tile)] text-fg2"><Icon size={20} /></span>
        <p className="text-sm text-fg2">{text}</p>
        {action}
      </div>
    </div>
  );
}

export const ErrorState = ({ onRetry }: { onRetry?: () => void }) => (
  <Empty
    Icon={AlertTriangle}
    text="Couldn't load this widget."
    action={onRetry && <button onClick={onRetry} className="tap rounded-full bg-[var(--sel)] px-4 py-1.5 text-xs font-medium hover:bg-[var(--sel)]">Try again</button>}
  />
);

const ToastCtx = createContext<(msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; msg: string }[]>([]);
  const push = useCallback((msg: string) => {
    const id = Date.now() + Math.random();
    setItems((i) => [...i, { id, msg }]);
    setTimeout(() => setItems((i) => i.filter((x) => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="no-print fixed bottom-24 right-4 z-[60] flex flex-col items-end gap-2 md:bottom-6 md:right-6" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="tip rounded-full px-4 py-2 text-sm"
            >
              {t.msg}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
