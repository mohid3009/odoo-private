const COLORS: Record<string, string> = {
  // subscription
  draft: "bg-slate-200 text-slate-800", quotation: "bg-blue-100 text-blue-800", confirmed: "bg-sky-100 text-sky-800",
  active: "bg-green-100 text-green-800", paused: "bg-amber-100 text-amber-800", closed: "bg-slate-300 text-slate-700",
  // invoice
  paid: "bg-green-100 text-green-800", cancelled: "bg-red-100 text-red-800",
  // odoo sync + notification
  synced: "bg-green-100 text-green-800", pending: "bg-amber-100 text-amber-800", skipped: "bg-slate-200 text-slate-700",
  error: "bg-red-100 text-red-800", sent: "bg-green-100 text-green-800", delivered: "bg-green-100 text-green-800",
  read: "bg-green-100 text-green-800", failed: "bg-red-100 text-red-800", queued: "bg-amber-100 text-amber-800",
  // payment attempts
  completed: "bg-green-100 text-green-800", reversed: "bg-slate-300 text-slate-700",
  // discount rule state
  scheduled: "bg-blue-100 text-blue-800", expired: "bg-slate-300 text-slate-700", exhausted: "bg-amber-100 text-amber-800", inactive: "bg-slate-200 text-slate-700",
  // roles
  admin: "bg-teal-100 text-teal-800", staff: "bg-blue-100 text-blue-800", customer: "bg-slate-200 text-slate-800",
};

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${COLORS[status] ?? "bg-slate-200 text-slate-800"}`}>{status}</span>;
}
