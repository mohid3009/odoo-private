import CrudPage, { CrudConfig } from "../../components/CrudPage";

const templates: CrudConfig<any> = {
  title: "Quotation templates", noun: "template", writeRoles: ["admin", "staff"], endpoint: "/api/quotation-templates/", queryKey: "quotation-templates",
  columns: [
    { key: "name", header: "Name" },
    { key: "plan_name", header: "Plan" },
    { key: "validity_days", header: "Valid for", render: (r) => `${r.validity_days} days` },
    { key: "lines", header: "Lines", render: (r) => r.lines.map((l: any) => `${l.product_name} × ${l.quantity}`).join(", ") || "—" },
    { key: "is_active", header: "Active", render: (r) => (r.is_active ? "Yes" : "—") },
  ],
  fields: [
    { name: "name", label: "Name", required: true },
    { name: "plan", label: "Plan", type: "select", required: true, optionsFrom: { endpoint: "/api/plans/", label: (p) => p.name } },
    { name: "validity_days", label: "Quotation valid for (days)", type: "number", required: true },
    {
      name: "lines", label: "Lines", type: "lines", addLabel: "Add line",
      hint: "Prices are filled in when a subscription is created from the template.",
      lineFields: [
        { name: "product", label: "Product", type: "select", required: true, optionsFrom: { endpoint: "/api/products/", label: (p) => p.name } },
        {
          name: "variant", label: "Variant", type: "select", placeholder: "No variant",
          optionsFrom: {
            endpoint: "/api/products/", label: (p) => p.name,
            expand: (rows) => rows.flatMap((p) => p.variants.map((v: any) => ({ value: String(v.id), label: `${p.name} / ${v.attribute}=${v.value}` }))),
          },
        },
        { name: "quantity", label: "Qty", type: "number", required: true },
      ],
    },
    { name: "is_active", label: "Active", type: "checkbox" },
  ],
  defaults: { name: "", plan: "", validity_days: "30", lines: [], is_active: true },
  toForm: (r) => ({
    ...r,
    plan: String(r.plan),
    lines: r.lines.map((l: any) => ({ _id: String(l.id), product: String(l.product), variant: l.variant ? String(l.variant) : "", quantity: String(l.quantity) })),
  }),
  toPayload: (v) => ({
    ...v,
    lines: (v.lines ?? []).map((l: any) => ({ product: Number(l.product), variant: l.variant ? Number(l.variant) : null, quantity: Number(l.quantity) })),
  }),
};

export const TemplatesPage = () => <CrudPage config={templates} />;
