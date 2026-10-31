import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../api/client";
import DataTable, { Column } from "../../components/DataTable";
import StatusBadge from "../../components/StatusBadge";

const err = (e: unknown) => (e instanceof ApiError && (e.body as any)?.detail ? (e.body as any).detail : "That did not work.");
const sel = "rounded border px-2 py-1 text-sm";

function ProviderBanner() {
  const { data } = useQuery({ queryKey: ["notifications", "provider"], queryFn: () => api.get<any>("/api/notifications/provider-status/") });
  if (!data) return null;
  const bad = !data.configured;
  return (
    <p role="status" className={`rounded px-3 py-2 text-sm ${bad ? "bg-red-50 text-red-800" : "bg-slate-100 text-slate-700"}`}>
      WhatsApp provider: <strong>{data.provider}</strong>
      {data.provider === "console" && " — messages are written to the server log, nothing leaves the machine."}
      {data.sandbox && " — Twilio sandbox: only phones that joined the sandbox receive messages."}
      {bad && " — not configured; WhatsApp messages are skipped (provider disabled)."}
    </p>
  );
}

function LogTab() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [event, setEvent] = useState("");
  const [msg, setMsg] = useState("");
  const params: Record<string, string> = {};
  if (status) params.status = status;
  if (channel) params.channel = channel;
  if (event) params.event = event;

  const retry = async (id: number) => {
    setMsg("");
    try {
      const r = await api.post<any>(`/api/notifications/logs/${id}/retry/`);
      setMsg(r.status === "sent" ? "Message sent." : `Retry result: ${r.status}${r.error ? ` — ${r.error}` : ""}`);
      qc.invalidateQueries({ queryKey: ["notification-logs"] });
    } catch (e) {
      setMsg(err(e));
    }
  };

  const columns: Column<any>[] = [
    { key: "created_at", header: "When", render: (r) => new Date(r.created_at).toLocaleString() },
    { key: "event_label", header: "Event" },
    { key: "channel", header: "Channel", render: (r) => `${r.channel} (${r.provider})` },
    { key: "recipient", header: "To", render: (r) => r.recipient_address || r.recipient_email },
    {
      key: "status", header: "Status",
      render: (r) => (
        <span>
          <StatusBadge status={r.status} />
          {r.skip_reason && <span className="ml-1 text-xs text-slate-500">{r.skip_reason.replace("_", " ")}</span>}
          {r.error && <span className="block max-w-xs truncate text-xs text-red-700" title={r.error}>{r.error}</span>}
        </span>
      ),
    },
    { key: "attempts", header: "Tries" },
    {
      key: "actions", header: "",
      render: (r) => r.status === "failed" && <button className="rounded border px-2 py-0.5 text-xs" onClick={() => retry(r.id)}>Retry</button>,
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Filter by status" className={sel} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["queued", "sent", "failed", "skipped"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select aria-label="Filter by channel" className={sel} value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">All channels</option>
          <option value="email">email</option>
          <option value="whatsapp">whatsapp</option>
        </select>
        <input aria-label="Filter by event code" placeholder="Event code, e.g. INVOICE_READY" className={sel} value={event} onChange={(e) => setEvent(e.target.value.trim().toUpperCase())} />
      </div>
      {msg && <p role="status" className="rounded bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      <DataTable<any> queryKey="notification-logs" endpoint="/api/notifications/logs/" columns={columns} params={params} empty="No messages match." />
    </div>
  );
}

function TemplateEditor({ body, onSave }: { body: string; onSave: (b: string) => void }) {
  const [v, setV] = useState(body);
  return (
    <div className="flex gap-2">
      <textarea aria-label="Message template" rows={2} className="w-full rounded border px-2 py-1" value={v} onChange={(e) => setV(e.target.value)} />
      <button className="self-start rounded border px-3 py-1 disabled:opacity-40" disabled={v === body || !v.trim()} onClick={() => onSave(v)}>Save</button>
    </div>
  );
}

function EventsTab() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["notifications", "events"], queryFn: () => api.get<any[]>("/api/notifications/events/") });
  const [msg, setMsg] = useState("");
  const save = async (code: string, patch: Record<string, unknown>) => {
    setMsg("");
    try {
      await api.patch(`/api/notifications/events/${code}/`, patch);
      qc.invalidateQueries({ queryKey: ["notifications", "events"] });
      setMsg("Saved.");
    } catch (e) {
      setMsg(err(e));
    }
  };
  if (!data) return <p className="py-6 text-slate-500">Loading…</p>;
  return (
    <div className="space-y-3">
      {msg && <p role="status" className="rounded bg-slate-100 px-3 py-2 text-sm">{msg}</p>}
      {data.map((e) => (
        <div key={e.code} className="rounded border bg-white p-3 text-sm">
          <div className="mb-2 flex flex-wrap items-center gap-4">
            <span className="font-medium">{e.label}</span>
            <code className="text-xs text-slate-500">{e.code}</code>
            <label className="flex items-center gap-1"><input type="checkbox" checked={e.enabled_email} onChange={(ev) => save(e.code, { enabled_email: ev.target.checked })} /> Email</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={e.enabled_whatsapp} onChange={(ev) => save(e.code, { enabled_whatsapp: ev.target.checked })} /> WhatsApp</label>
          </div>
          <TemplateEditor key={e.template_body} body={e.template_body} onSave={(b) => save(e.code, { template_body: b })} />
        </div>
      ))}
    </div>
  );
}

function ToolsTab() {
  const qc = useQueryClient();
  const [channel, setChannel] = useState("whatsapp");
  const [to, setTo] = useState("");
  const [body, setBody] = useState("Test message from Brightloop");
  const [result, setResult] = useState("");
  const [reminders, setReminders] = useState("");
  const [busy, setBusy] = useState(false);

  const test = async () => {
    setResult(""); setBusy(true);
    try {
      const r = await api.post<any>("/api/notifications/test-send/", { channel, to, body });
      setResult(r.ok ? `Sent via ${r.provider} (${r.detail}).` : `Failed via ${r.provider}: ${r.detail}`);
    } catch (e) {
      setResult(e instanceof ApiError && (e.body as any)?.to ? String((e.body as any).to) : err(e));
    } finally {
      setBusy(false);
    }
  };
  const runReminders = async () => {
    setReminders("");
    try {
      const r = await api.post<any>("/api/notifications/run-reminders/");
      setReminders(`${r.as_of}: ${r.due_soon} due soon, ${r.overdue} overdue, ${r.expiring} expiring — new messages only; reruns send none.`);
      qc.invalidateQueries({ queryKey: ["notification-logs"] });
    } catch (e) {
      setReminders(err(e));
    }
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="space-y-2 rounded border bg-white p-4 text-sm">
        <h2 className="font-semibold">Test send</h2>
        <select aria-label="Channel" className={sel} value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="whatsapp">whatsapp</option>
          <option value="email">email</option>
        </select>
        <input aria-label="Recipient" className={`${sel} block w-full`} placeholder={channel === "email" ? "name@example.com" : "+919876543210"} value={to} onChange={(e) => setTo(e.target.value)} />
        <textarea aria-label="Message" rows={3} className="w-full rounded border px-2 py-1" value={body} onChange={(e) => setBody(e.target.value)} />
        <button className="rounded bg-indigo-600 px-3 py-1 text-white disabled:opacity-40" disabled={busy || !to || !body} onClick={test}>Send test</button>
        {result && <p role="status">{result}</p>}
      </section>
      <section className="space-y-2 rounded border bg-white p-4 text-sm">
        <h2 className="font-semibold">Reminders</h2>
        <p className="text-slate-600">Scans for invoices due soon or overdue and subscriptions about to expire. Also runs after every billing run.</p>
        <button className="rounded border px-3 py-1" onClick={runReminders}>Run reminders now</button>
        {reminders && <p role="status">{reminders}</p>}
      </section>
    </div>
  );
}

const TABS = [["log", "Message log"], ["events", "Events & templates"], ["tools", "Test & reminders"]] as const;

export default function Notifications() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("log");
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Notifications</h1>
      <ProviderBanner />
      <div className="flex gap-2 border-b" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`-mb-px border-b-2 px-3 py-1.5 text-sm ${tab === k ? "border-indigo-600 font-medium" : "border-transparent text-slate-600"}`}>{label}</button>
        ))}
      </div>
      {tab === "log" && <LogTab />}
      {tab === "events" && <EventsTab />}
      {tab === "tools" && <ToolsTab />}
    </div>
  );
}
