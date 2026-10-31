import { useNavigate } from "react-router-dom";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

// Customer portal: /api/subscriptions/ is already scoped to the caller's own rows server-side.
const columns: Column<any>[] = [
  { key: "number", header: "Number", render: (r) => <span className="font-medium text-indigo-700">{r.number}</span> },
  { key: "plan_name", header: "Plan" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "start_date", header: "Start" },
  { key: "next_invoice_date", header: "Next invoice", render: (r) => r.next_invoice_date ?? "—" },
  { key: "lines_total", header: "Total (pre-tax)", render: (r) => <MoneyText value={r.lines_total} /> },
];

export default function MySubscriptions() {
  const navigate = useNavigate();
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">My subscriptions</h1>
      <DataTable queryKey="my-subscriptions" endpoint="/api/subscriptions/" columns={columns} empty="You have no subscriptions yet."
        onRowClick={(r) => navigate(`/my-subscriptions/${r.id}`)} />
    </div>
  );
}
