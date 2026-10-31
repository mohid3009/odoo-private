import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import DataTable, { Column } from "../../components/DataTable";

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in the browser's local time

const columns: Column<any>[] = [
  { key: "id", header: "Run" },
  { key: "as_of_date", header: "Billing date" },
  { key: "started_at", header: "Started", render: (r) => new Date(r.started_at).toLocaleString() },
  { key: "triggered_by_email", header: "By", render: (r) => r.triggered_by_email || "system" },
  { key: "created_count", header: "Created" },
  { key: "skipped_count", header: "Skipped" },
  { key: "error_count", header: "Errors", render: (r) => <span className={r.error_count ? "font-medium text-red-700" : ""}>{r.error_count}</span> },
];

export default function Billing() {
  const qc = useQueryClient();
  const [asOf, setAsOf] = useState(today());
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [log, setLog] = useState("");
  const [error, setError] = useState("");

  const run = async () => {
    setBusy(true); setError(""); setLog(""); setResult(null);
    try {
      const r = await api.post<any>("/api/billing/run/", { as_of: asOf });
      setResult(r);
      if (r.errors > 0) setLog((await api.get<any>(`/api/billing/runs/${r.run_id}/`)).log);
      qc.invalidateQueries({ queryKey: ["billing-runs"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
    } catch (e) {
      setError(e instanceof ApiError && (e.body as any)?.as_of ? `Billing date: ${(e.body as any).as_of}` : "The billing run failed to start.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="max-w-xl space-y-3">
        <h1 className="text-xl font-semibold">Run billing</h1>
        <p className="text-sm text-slate-600">
          Creates a <strong>draft</strong> invoice for every active subscription period that is due on or before the billing date. Safe to run more than once: a period is never billed twice.
        </p>
        <div className="flex flex-wrap items-end gap-3 rounded border bg-white p-4">
          <div>
            <label htmlFor="as-of" className="mb-1 block text-sm font-medium">Billing date</label>
            <input id="as-of" type="date" className="rounded border px-3 py-2" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </div>
          <button className="rounded bg-indigo-600 px-4 py-2 font-medium text-white disabled:opacity-50" disabled={busy || !asOf} onClick={run}>
            {busy ? "Running…" : "Run billing"}
          </button>
        </div>
        {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {result && (
          <div role="status" className="rounded border bg-white p-4 text-sm">
            <p className="font-medium">Run #{result.run_id} for {result.as_of_date}</p>
            <p className="mt-1">
              <span className="font-semibold text-green-700">{result.created}</span> invoice{result.created === 1 ? "" : "s"} created ·{" "}
              <span className="font-semibold">{result.skipped}</span> skipped (already billed) ·{" "}
              <span className={`font-semibold ${result.errors ? "text-red-700" : ""}`}>{result.errors}</span> error{result.errors === 1 ? "" : "s"}
            </p>
            {result.created > 0 && <p className="mt-2"><Link className="text-indigo-700" to="/invoices?status=draft">Review the new drafts →</Link></p>}
            {log && <pre className="mt-2 whitespace-pre-wrap rounded bg-red-50 p-2 text-xs text-red-800">{log}</pre>}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Run history</h2>
        <DataTable<any> queryKey="billing-runs" endpoint="/api/billing/runs/" columns={columns} empty="No billing runs yet." />
      </section>
    </div>
  );
}
