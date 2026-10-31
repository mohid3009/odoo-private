import { useState } from "react";

// Two-step click for destructive/irreversible actions.
export default function ConfirmButton({ label, confirmText = "Are you sure?", onConfirm, danger }: { label: string; confirmText?: string; onConfirm: () => void | Promise<void>; danger?: boolean }) {
  const [armed, setArmed] = useState(false);
  const base = "rounded border px-3 py-1 text-sm";
  if (!armed) return <button className={`${base} ${danger ? "border-red-300 text-red-700" : ""}`} onClick={() => setArmed(true)}>{label}</button>;
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      {confirmText}
      <button className={`${base} bg-red-600 text-white`} onClick={async () => { await onConfirm(); setArmed(false); }}>Yes</button>
      <button className={base} onClick={() => setArmed(false)}>No</button>
    </span>
  );
}
