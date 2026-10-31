import { NavLink, Outlet } from "react-router-dom";
import CrudPage, { CrudConfig } from "../../components/CrudPage";
import MoneyText from "../../components/MoneyText";
import StatusBadge from "../../components/StatusBadge";

const yesNo = (b: boolean) => (b ? "Yes" : "—");
const active = { key: "is_active", header: "Active", render: (r: any) => yesNo(r.is_active) };
const sync = { key: "odoo_sync_status", header: "Odoo", render: (r: any) => <StatusBadge status={r.odoo_sync_status} /> };

export function CatalogShell() {
  const tab = ({ isActive }: { isActive: boolean }) =>
    `rounded px-3 py-1 text-sm ${isActive ? "bg-sky-600 text-white" : "border bg-white text-slate-700"}`;
  return (
    <div className="space-y-4">
      <nav className="flex flex-wrap gap-2" aria-label="Catalog sections">
        <NavLink to="/catalog/products" className={tab}>Products</NavLink>
        <NavLink to="/catalog/plans" className={tab}>Plans</NavLink>
        <NavLink to="/catalog/taxes" className={tab}>Taxes</NavLink>
        <NavLink to="/catalog/terms" className={tab}>Payment terms</NavLink>
      </nav>
      <Outlet />
    </div>
  );
}

// ---- Taxes ----
const taxes: CrudConfig<any> = {
  title: "Taxes", noun: "tax", endpoint: "/api/taxes/", queryKey: "taxes",
  columns: [{ key: "name", header: "Name" }, { key: "rate", header: "Rate", render: (r) => `${r.rate}%` }, active, sync],
  fields: [
    { name: "name", label: "Name", required: true, placeholder: "GST 18%" },
    { name: "rate", label: "Rate (%)", type: "money", required: true, hint: "0–100" },
    { name: "is_active", label: "Active", type: "checkbox" },
  ],
  defaults: { name: "", rate: "", is_active: true },
};
export const TaxesPage = () => <CrudPage config={taxes} />;

// ---- Payment terms ----
const terms: CrudConfig<any> = {
  title: "Payment terms", noun: "payment term", endpoint: "/api/payment-terms/", queryKey: "payment-terms",
  columns: [{ key: "name", header: "Name" }, { key: "days", header: "Days to pay" }, { key: "is_default", header: "Default", render: (r) => yesNo(r.is_default) }],
  fields: [
    { name: "name", label: "Name", required: true, placeholder: "Net 15" },
    { name: "days", label: "Days until due", type: "number", required: true },
    { name: "is_default", label: "Default term (clears the flag on the others)", type: "checkbox" },
  ],
  defaults: { name: "", days: "0", is_default: false },
};
export const TermsPage = () => <CrudPage config={terms} />;

// ---- Products (with variants) ----
const products: CrudConfig<any> = {
  title: "Products", noun: "product", endpoint: "/api/products/", queryKey: "products",
  columns: [
    { key: "name", header: "Name" },
    { key: "type", header: "Type" },
    { key: "sales_price", header: "Sales price", render: (r) => <MoneyText value={r.sales_price} /> },
    { key: "variants", header: "Variants", render: (r) => r.variants.map((v: any) => `${v.attribute}=${v.value} (+${v.extra_price})`).join(", ") || "—" },
    active, sync,
  ],
  fields: [
    { name: "name", label: "Name", required: true },
    { name: "type", label: "Type", type: "select", options: ["service", "software", "addon", "physical"].map((v) => ({ value: v, label: v })) },
    { name: "sales_price", label: "Sales price", type: "money", required: true },
    { name: "cost_price", label: "Cost price", type: "money" },
    { name: "taxes", label: "Taxes", type: "multiselect", optionsFrom: { endpoint: "/api/taxes/", label: (t) => `${t.name}` } },
    {
      name: "variants", label: "Variants", type: "lines", addLabel: "Add variant",
      hint: "e.g. Brand / Odoo / 560.00. The unit price becomes sales price + extra.",
      lineFields: [
        { name: "attribute", label: "Attribute", required: true },
        { name: "value", label: "Value", required: true },
        { name: "extra_price", label: "Extra price", type: "money", required: true },
      ],
    },
    { name: "notes", label: "Notes", type: "textarea" },
    { name: "is_active", label: "Active", type: "checkbox" },
  ],
  defaults: { name: "", type: "software", sales_price: "", cost_price: "0.00", taxes: [], variants: [], notes: "", is_active: true },
  toForm: (r) => ({
    ...r,
    taxes: r.taxes.map(String),
    variants: r.variants.map((v: any) => ({ _id: String(v.id), attribute: v.attribute, value: v.value, extra_price: v.extra_price })),
  }),
  toPayload: (v) => ({
    ...v,
    cost_price: v.cost_price || "0.00",
    taxes: (v.taxes ?? []).map(Number),
    variants: (v.variants ?? []).map(({ _id, ...rest }: any) => (_id ? { id: Number(_id), ...rest } : rest)),
  }),
};
export const ProductsPage = () => <CrudPage config={products} />;

// ---- Plans ----
const plans: CrudConfig<any> = {
  title: "Plans", noun: "plan", endpoint: "/api/plans/", queryKey: "plans",
  columns: [
    { key: "name", header: "Plan" },
    { key: "product_name", header: "Product" },
    { key: "price", header: "Price", render: (r) => <MoneyText value={r.price} /> },
    { key: "billing_period", header: "Period" },
    { key: "min_quantity", header: "Min qty" },
    { key: "window", header: "Available", render: (r) => `${r.available_from ?? "…"} → ${r.available_to ?? "…"}` },
    { key: "flags", header: "Flags", render: (r) => [r.auto_close && "auto-close", r.allow_early_close && "early close", r.allow_pause && "pause", r.allow_renew && "renew"].filter(Boolean).join(", ") || "—" },
    active,
  ],
  fields: [
    { name: "name", label: "Name", required: true },
    { name: "product", label: "Primary product", type: "select", required: true, optionsFrom: { endpoint: "/api/products/", label: (p) => p.name } },
    { name: "price", label: "Price per unit per period", type: "money", required: true },
    { name: "billing_period", label: "Billing period", type: "select", options: ["daily", "weekly", "monthly", "yearly"].map((v) => ({ value: v, label: v })) },
    { name: "min_quantity", label: "Minimum quantity", type: "number", required: true },
    { name: "available_from", label: "Available from", type: "date" },
    { name: "available_to", label: "Available to", type: "date" },
    { name: "auto_close", label: "Auto-close at expiry", type: "checkbox" },
    { name: "allow_early_close", label: "Allow early close", type: "checkbox" },
    { name: "allow_pause", label: "Allow pause", type: "checkbox" },
    { name: "allow_renew", label: "Allow renew", type: "checkbox" },
    { name: "is_active", label: "Active", type: "checkbox" },
  ],
  defaults: { name: "", product: "", price: "", billing_period: "monthly", min_quantity: "1", available_from: "", available_to: "", auto_close: false, allow_early_close: false, allow_pause: false, allow_renew: false, is_active: true },
  toForm: (r) => ({ ...r, product: String(r.product), available_from: r.available_from ?? "", available_to: r.available_to ?? "" }),
};
export const PlansPage = () => <CrudPage config={plans} />;
