import PageLoader from "../../components/PageLoader";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import MoneyText from "../../components/MoneyText";

// Browser "Save as PDF" is the PDF (D-016). Layout/nav and the toolbar carry the no-print class (index.css).
export default function InvoicePrint() {
  const { id } = useParams();
  const { data: inv, isLoading, isError } = useQuery({ queryKey: ["invoices", "print", id], queryFn: () => api.get<any>(`/api/invoices/${id}/print/`) });

  if (isLoading) return <PageLoader />;
  if (isError || !inv) return <p className="py-6 text-red-700">Invoice not found.</p>;
  const c = inv.customer_details;

  return (
    <div className="mx-auto max-w-3xl bg-white p-6 sm:p-10">
      <div className="no-print mb-6 flex items-center gap-3">
        <Link className="text-sm text-sky-700" to={`/invoices/${id}`}>← Back</Link>
        <button className="ml-auto rounded bg-sky-600 px-4 py-1 text-sm text-white" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>

      <header className="flex items-start justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-semibold">{inv.seller.name}</h1>
          <p className="text-sm text-slate-500">Subscription billing</p>
        </div>
        <div className="text-right">
          <p className="text-xl font-semibold">{inv.number ? "INVOICE" : "DRAFT INVOICE"}</p>
          <p className="text-sm">{inv.number ?? `#${inv.id}`}</p>
        </div>
      </header>

      <section className="mt-5 grid grid-cols-2 gap-6 text-sm">
        <div>
          <h2 className="text-xs uppercase text-slate-500">Bill to</h2>
          <p className="font-medium">{c.company_name || c.name || c.email}</p>
          {c.company_name && c.name && <p>{c.name}</p>}
          <p>{c.email}</p>
          {c.phone && <p>{c.phone}</p>}
          {c.address && <p className="whitespace-pre-line">{c.address}</p>}
        </div>
        <dl className="grid grid-cols-2 gap-y-1 text-right">
          <dt className="text-slate-500">Invoice date</dt><dd>{inv.invoice_date}</dd>
          <dt className="text-slate-500">Due date</dt><dd>{inv.due_date}</dd>
          <dt className="text-slate-500">Service period</dt><dd>{inv.period_start} → {inv.period_end}</dd>
          <dt className="text-slate-500">Subscription</dt><dd>{inv.subscription_number}</dd>
        </dl>
      </section>

      <table className="mt-6 w-full text-left text-sm">
        <thead>
          <tr className="border-y bg-slate-50">{["Description", "Qty", "Unit price", "Tax", "Amount"].map((h, i) => <th key={h} className={`px-2 py-2 font-medium ${i > 0 ? "text-right" : ""}`}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {inv.lines.map((l: any) => (
            <tr key={l.id} className="border-b">
              <td className="px-2 py-2">{l.description}</td>
              <td className="px-2 py-2 text-right">{l.quantity}</td>
              <td className="px-2 py-2 text-right"><MoneyText value={l.unit_price} /></td>
              <td className="px-2 py-2 text-right">{l.tax_rate}%</td>
              <td className="px-2 py-2 text-right"><MoneyText value={l.line_subtotal} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl className="ml-auto mt-4 grid max-w-xs grid-cols-2 gap-y-1 text-sm">
        <dt>Subtotal</dt><dd className="text-right"><MoneyText value={inv.subtotal} /></dd>
        {Number(inv.discount_total) > 0 && <><dt>Discounts</dt><dd className="text-right"><MoneyText value={`-${inv.discount_total}`} /></dd></>}
        <dt>Tax</dt><dd className="text-right"><MoneyText value={inv.tax_total} /></dd>
        <dt className="border-t pt-1 font-semibold">Total</dt><dd className="border-t pt-1 text-right font-semibold"><MoneyText value={inv.total} /></dd>
        {Number(inv.amount_paid) > 0 && <><dt>Paid</dt><dd className="text-right"><MoneyText value={inv.amount_paid} /></dd></>}
        <dt className="font-semibold">Balance due</dt><dd className="text-right font-semibold"><MoneyText value={inv.amount_due} /></dd>
      </dl>

      <p className="mt-10 text-center text-xs text-slate-500">Thank you for your business.</p>
    </div>
  );
}
