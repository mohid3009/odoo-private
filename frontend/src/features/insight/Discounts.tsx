import { Link } from "react-router-dom";
import CrudPage, { CrudConfig } from "../../components/CrudPage";
import StatusBadge from "../../components/StatusBadge";

const blankToNull = (v: any) => (v === "" || v === undefined ? null : v);

// Rules are created by admins; staff can read them (CrudPage hides the write controls for them, the server enforces it).
const discounts: CrudConfig<any> = {
  title: "Discounts", noun: "discount", endpoint: "/api/discounts/", queryKey: "discounts",
  columns: [
    { key: "name", header: "Name", render: (r) => <span>{r.name}{r.code ? <span className="ml-1 text-xs text-slate-500">({r.code})</span> : null}</span> },
    { key: "value", header: "Value", render: (r) => (r.type === "percent" ? `${Number(r.value)}%` : `₹${r.value}`) },
    { key: "scope", header: "Applies to", render: (r) => (r.scope === "product" ? `${r.products.length} product${r.products.length === 1 ? "" : "s"}` : "Whole subscription (attach)") },
    { key: "window", header: "Valid", render: (r) => `${r.start_date ?? "…"} → ${r.end_date ?? "…"}` },
    { key: "mins", header: "Minimums", render: (r) => [r.min_quantity && `qty ≥ ${r.min_quantity}`, r.min_purchase_amount && `₹${r.min_purchase_amount}`].filter(Boolean).join(", ") || "—" },
    {
      key: "used_count", header: "Used",
      render: (r) => <Link className="text-sky-700" to={`/discounts/${r.id}/redemptions`} onClick={(e) => e.stopPropagation()}>{r.used_count} / {r.usage_limit ?? "∞"}</Link>,
    },
    { key: "state", header: "State", render: (r) => <StatusBadge status={r.state} /> },
  ],
  fields: [
    { name: "name", label: "Name", required: true, placeholder: "Launch 10%" },
    { name: "code", label: "Code (optional)", hint: "Must be unique if set." },
    { name: "type", label: "Type", type: "select", options: [{ value: "percent", label: "Percent" }, { value: "fixed", label: "Fixed amount" }] },
    { name: "value", label: "Value", type: "money", required: true, hint: "Percent: above 0 up to 100. Fixed: an amount in ₹." },
    {
      name: "scope", label: "Applies to", type: "select",
      options: [{ value: "product", label: "Specific products (applied automatically)" }, { value: "subscription", label: "Whole subscription (attached by staff)" }],
    },
    { name: "products", label: "Products (for product discounts)", type: "multiselect", optionsFrom: { endpoint: "/api/products/", label: (p) => p.name } },
    { name: "min_purchase_amount", label: "Minimum purchase amount", type: "money", hint: "Leave empty for none. For a product discount it is the line amount." },
    { name: "min_quantity", label: "Minimum quantity", type: "number", hint: "Leave empty for none." },
    { name: "start_date", label: "Valid from", type: "date" },
    { name: "end_date", label: "Valid until", type: "date" },
    { name: "usage_limit", label: "Usage limit (invoices)", type: "number", hint: "Leave empty for unlimited. Counted once per invoice." },
    { name: "is_active", label: "Active", type: "checkbox" },
  ],
  defaults: {
    name: "", code: "", type: "percent", value: "", scope: "product", products: [], min_purchase_amount: "", min_quantity: "",
    start_date: "", end_date: "", usage_limit: "", is_active: true,
  },
  toForm: (r) => ({
    ...r, code: r.code ?? "", products: r.products.map(String), min_purchase_amount: r.min_purchase_amount ?? "", min_quantity: r.min_quantity ?? "",
    start_date: r.start_date ?? "", end_date: r.end_date ?? "", usage_limit: r.usage_limit ?? "",
  }),
  toPayload: (v) => ({
    ...v,
    code: blankToNull(v.code),
    products: v.scope === "subscription" ? [] : (v.products ?? []).map(Number),
    min_purchase_amount: blankToNull(v.min_purchase_amount),
    min_quantity: blankToNull(v.min_quantity),
    usage_limit: blankToNull(v.usage_limit),
  }),
};

export const DiscountsPage = () => <CrudPage config={discounts} />;
