import { Link, useParams } from "react-router-dom";
import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";

const columns: Column<any>[] = [
  { key: "invoice_number", header: "Invoice", render: (r) => <Link className="text-indigo-700" to={`/invoices/${r.invoice}`}>{r.invoice_number ?? `Draft #${r.invoice}`}</Link> },
  { key: "subscription_number", header: "Subscription" },
  { key: "customer_email", header: "Customer" },
  { key: "amount", header: "Saved", render: (r) => <MoneyText value={r.amount} /> },
  { key: "created_at", header: "When", render: (r) => new Date(r.created_at).toLocaleString() },
];

// Audit view (FR-DISC-05): every invoice a rule was applied to.
export default function DiscountRedemptions() {
  const { id } = useParams();
  return (
    <div className="space-y-3">
      <Link className="text-sm text-indigo-700" to="/discounts">← Discounts</Link>
      <h1 className="text-xl font-semibold">Where this discount was used</h1>
      <DataTable<any> queryKey={`discount-${id}-redemptions`} endpoint={`/api/discounts/${id}/redemptions/`} columns={columns} empty="Not used on any invoice yet." />
    </div>
  );
}
