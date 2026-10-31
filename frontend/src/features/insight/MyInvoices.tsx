import { Link } from "react-router-dom";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

// Customer portal v1: /api/invoices/ only returns the caller's own, non-draft invoices (server-scoped).
const columns: Column<any>[] = [
  { key: "number", header: "Invoice", render: (r) => <Link className="font-medium text-indigo-700" to={`/invoices/${r.id}/print`}>{r.number}</Link> },
  { key: "subscription_number", header: "Subscription" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  { key: "due_date", header: "Due", render: (r) => (r.is_overdue ? <span className="font-medium text-red-700">{r.due_date} · overdue</span> : r.due_date) },
  { key: "total", header: "Total", render: (r) => <MoneyText value={r.total} /> },
  { key: "amount_due", header: "Balance", render: (r) => <MoneyText value={r.amount_due} /> },
];

export default function MyInvoices() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">My invoices</h1>
      <DataTable queryKey="my-invoices" endpoint="/api/invoices/" columns={columns} empty="You have no invoices yet." />
    </div>
  );
}
