import DataTable, { Column } from "../../components/DataTable";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

// Customer portal: payment history (read-only, from own invoices' payments).
const columns: Column<any>[] = [
  { key: "invoice_number", header: "Invoice" },
  { key: "payment_date", header: "Date" },
  { key: "amount", header: "Amount", render: (r) => <MoneyText value={r.amount} /> },
  { key: "method", header: "Method" },
  { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status ?? "recorded"} /> },
];

export default function PaymentHistory() {
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Payment history</h1>
      <DataTable queryKey="payment-history" endpoint="/api/payments/" columns={columns} empty="No payments yet." />
    </div>
  );
}
