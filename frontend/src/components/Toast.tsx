import { Component, ReactNode, useEffect, useState } from "react";

// Global error toasts for what a page cannot show inline: network failures, 5xx, an expired session.
// 4xx validation errors stay next to the form/button that caused them (pages already render those).
type Item = { id: number; text: string };
let next = 1;
const listeners = new Set<(t: Item) => void>();

export function toast(text: string) {
  const item = { id: next++, text };
  listeners.forEach((l) => l(item));
}

export function Toaster() {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    const add = (t: Item) => {
      setItems((xs) => (xs.some((x) => x.text === t.text) ? xs : [...xs, t])); // same message twice → one toast
      setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== t.id)), 6000);
    };
    listeners.add(add);
    return () => { listeners.delete(add); };
  }, []);
  return (
    <div aria-live="assertive" className="no-print fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} role="alert" className="flex items-start gap-3 rounded bg-red-700 px-4 py-3 text-sm text-white shadow-lg">
          <span className="flex-1">{t.text}</span>
          <button aria-label="Dismiss" className="opacity-80 hover:opacity-100" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))}>✕</button>
        </div>
      ))}
    </div>
  );
}

// A render crash shows a recoverable page instead of a blank screen.
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto max-w-md py-16 text-center">
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="mt-2 text-slate-600">The page hit an unexpected error. Your data is safe.</p>
        <button className="mt-4 rounded bg-indigo-600 px-4 py-2 text-sm text-white" onClick={() => window.location.assign("/")}>Back to home</button>
      </div>
    );
  }
}
