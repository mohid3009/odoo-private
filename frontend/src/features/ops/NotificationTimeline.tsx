import PageLoader from "../../components/PageLoader";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Page } from "../../api/types";
import StatusBadge from "../../components/StatusBadge";

// Small "what was sent about this object" list for the invoice and subscription screens (staff + admin).
export default function NotificationTimeline({ objectType, objectId }: { objectType: "invoice" | "subscription"; objectId: number | string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["notifications", "timeline", objectType, objectId],
    queryFn: () => api.get<Page<any>>(`/api/notifications/logs/?object_type=${objectType}&object_id=${objectId}&page_size=50`),
  });

  return (
    <section aria-label="Notifications">
      <h2 className="mb-2 font-semibold">Notifications</h2>
      {isLoading && <PageLoader compact />}
      {isError && <p className="text-sm text-red-700">Could not load notifications.</p>}
      {data && data.results.length === 0 && <p className="text-sm text-slate-500">Nothing has been sent about this yet.</p>}
      {data && data.results.length > 0 && (
        <ol className="space-y-1 border-l-2 pl-4 text-sm">
          {data.results.map((n: any) => (
            <li key={n.id}>
              <span className="font-medium">{n.event_label}</span> · {n.channel} <StatusBadge status={n.status} />
              <span className="ml-2 text-slate-500">{n.recipient_address || n.recipient_email} · {new Date(n.sent_at ?? n.created_at).toLocaleString()}</span>
              {n.skip_reason && <span className="ml-2 text-xs text-slate-500">({n.skip_reason.replace("_", " ")})</span>}
              {n.status === "failed" && n.error && <span className="block text-xs text-red-700">{n.error}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
