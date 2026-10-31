import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import DataTable, { Column } from "../../components/DataTable";
import StatusBadge from "../../components/StatusBadge";

// Customer portal: notification preferences (PATCH /api/me/notification-settings/) + messages sent to me.
const columns: Column<any>[] = [
  { key: "event_label", header: "Message" },
  { key: "channel", header: "Channel" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "sent_at", header: "Sent", render: (r) => r.sent_at ?? "—" },
];

function Settings() {
  const qc = useQueryClient();
  const [msg, setMsg] = useState("");
  const { data } = useQuery({ queryKey: ["me", "notif-settings"], queryFn: () => api.get<any>("/api/me/notification-settings/") });
  const [phone, setPhone] = useState<string | null>(null);
  if (!data) return null;
  const save = async (patch: Record<string, unknown>) => {
    try {
      await api.patch("/api/me/notification-settings/", patch);
      await qc.invalidateQueries({ queryKey: ["me", "notif-settings"] });
      setMsg("Saved.");
    } catch (e) {
      setMsg(e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "Could not save — check the number format.");
    }
  };
  return (
    <section className="space-y-2 rounded border bg-white p-4">
      <h2 className="font-medium">Preferences</h2>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={data.email_notifications} onChange={(e) => save({ email_notifications: e.target.checked })} /> Email me about quotes, invoices and payments
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={data.whatsapp_opt_in} onChange={(e) => save({ whatsapp_opt_in: e.target.checked })} /> Also send WhatsApp messages
      </label>
      <div className="flex items-center gap-2 text-sm">
        <label htmlFor="wa">WhatsApp number</label>
        <input id="wa" className="rounded border px-2 py-1" placeholder="+91…" value={phone ?? data.whatsapp_number ?? ""} onChange={(e) => setPhone(e.target.value)} />
        <button className="rounded bg-indigo-600 px-3 py-1 text-white" onClick={() => save({ whatsapp_number: phone ?? data.whatsapp_number })}>Save number</button>
      </div>
      {msg && <p role="status" className="text-sm text-slate-600">{msg}</p>}
    </section>
  );
}

export default function MyNotifications() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Notifications</h1>
      <Settings />
      <DataTable queryKey="my-notifications" endpoint="/api/me/notifications/" columns={columns} empty="No messages yet." />
    </div>
  );
}
