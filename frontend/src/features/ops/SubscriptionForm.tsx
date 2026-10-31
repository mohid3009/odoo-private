import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFieldArray, useForm } from "react-hook-form";
import { api, ApiError } from "../../api/client";
import type { Page } from "../../api/types";
import { flatten } from "../../components/ResourceForm";
import MoneyText from "../../components/MoneyText";
import { centsToStr, toCents } from "../../lib/money";

const input = "w-full rounded border border-slate-300 px-3 py-2 focus:border-sky-500 focus:outline-none";
const MONEY = /^\d+(\.\d{1,2})?$/;

const list = <T,>(endpoint: string) =>
  useQuery({ queryKey: ["options", endpoint], queryFn: () => api.get<Page<T>>(`${endpoint}?page_size=200`) });

interface Line { _tax?: number[]; product: string; variant: string; quantity: string; unit_price: string }

// Bespoke on purpose (rule 10 exception): lines depend on the chosen plan/product/variant and need live totals.
export default function SubscriptionForm({ initial, onSaved, onCancel }: { initial?: any; onSaved: (sub: any) => void; onCancel?: () => void }) {
  const customers = list<any>("/api/customers/").data?.results ?? [];
  const plans = list<any>("/api/plans/").data?.results ?? [];
  const terms = list<any>("/api/payment-terms/").data?.results ?? [];
  const products = list<any>("/api/products/").data?.results ?? [];
  const [serverError, setServerError] = useState("");

  const form = useForm<any>({
    defaultValues: initial
      ? {
          customer: String(initial.customer), plan: String(initial.plan), start_date: initial.start_date,
          expiry_date: initial.expiry_date ?? "", payment_term: String(initial.payment_term), notes: initial.notes,
          lines: initial.lines.map((l: any): Line => ({
            _tax: l.taxes, product: String(l.product), variant: l.variant ? String(l.variant) : "", quantity: String(l.quantity), unit_price: l.unit_price,
          })),
        }
      : { customer: "", plan: "", start_date: "", expiry_date: "", payment_term: "", notes: "", lines: [] },
  });
  const { register, control, handleSubmit, setValue, setError, clearErrors, watch, formState: { errors, isSubmitting } } = form;
  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const plan = plans.find((p) => String(p.id) === watch("plan"));
  const lines: Line[] = watch("lines") ?? [];

  // Suggested price (D-001): plan price for the plan's primary product, otherwise the product's sales price, plus the variant extra.
  const suggest = (productId: string, variantId: string): string => {
    const product = products.find((p) => String(p.id) === productId);
    if (!product) return "";
    const base = plan && plan.product === product.id ? plan.price : product.sales_price;
    const extra = product.variants.find((v: any) => String(v.id) === variantId)?.extra_price ?? "0";
    return centsToStr((toCents(base) ?? 0) + (toCents(extra) ?? 0));
  };
  const reprice = (i: number, productId: string, variantId: string) => setValue(`lines.${i}.unit_price`, suggest(productId, variantId), { shouldDirty: true });

  const lineCents = (l: Line) => {
    const unit = toCents(l.unit_price);
    const qty = parseInt(l.quantity, 10);
    return unit === null || !qty || qty < 1 ? null : unit * qty;
  };
  const totalCents = lines.reduce((sum, l) => sum + (lineCents(l) ?? 0), 0);

  const submit = handleSubmit(async (v) => {
    setServerError("");
    const body = {
      customer: Number(v.customer), plan: Number(v.plan), start_date: v.start_date, expiry_date: v.expiry_date || null,
      ...(v.payment_term ? { payment_term: Number(v.payment_term) } : {}), notes: v.notes,
      lines: v.lines.map((l: Line) => ({
        product: Number(l.product), variant: l.variant ? Number(l.variant) : null, quantity: Number(l.quantity),
        ...(l.unit_price ? { unit_price: l.unit_price } : {}), ...(l._tax ? { taxes: l._tax } : {}),
      })),
    };
    try {
      const saved = initial ? await api.patch<any>(`/api/subscriptions/${initial.id}/`, body) : await api.post<any>("/api/subscriptions/", body);
      onSaved(saved);
    } catch (e) {
      if (e instanceof ApiError && e.body && typeof e.body === "object") {
        const flat = flatten(e.body);
        const known = ["customer", "plan", "start_date", "expiry_date", "payment_term", "notes", "lines"];
        let rest = "";
        for (const [k, m] of Object.entries(flat)) known.includes(k) ? setError(k, { message: m }) : (rest += `${m} `);
        if (rest) setServerError(rest.trim());
      } else setServerError("Network error. Please try again.");
    }
  });

  const select = (name: string, label: string, opts: { value: string; label: string }[], required = true) => (
    <div>
      <label htmlFor={`s-${name}`} className="mb-1 block text-sm font-medium">{label}{required && " *"}</label>
      <select id={`s-${name}`} className={input} {...register(name, { required: required ? `${label} is required.` : false })}>
        <option value="">Select…</option>
        {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {errors[name] && <p role="alert" className="mt-1 text-sm text-red-700">{String(errors[name]?.message)}</p>}
    </div>
  );
  const date = (name: string, label: string, required = false) => (
    <div>
      <label htmlFor={`s-${name}`} className="mb-1 block text-sm font-medium">{label}{required && " *"}</label>
      <input id={`s-${name}`} type="date" className={input} {...register(name, { required: required ? `${label} is required.` : false })} />
      {errors[name] && <p role="alert" className="mt-1 text-sm text-red-700">{String(errors[name]?.message)}</p>}
    </div>
  );

  return (
    // clearErrors first: the server's `lines` error has no field rule, so RHF would otherwise block every resubmit
    <form onSubmit={(e) => { clearErrors(); return submit(e); }} noValidate className="space-y-4">
      {serverError && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</p>}
      <div className="grid gap-4 sm:grid-cols-2">
        {select("customer", "Customer", customers.map((c) => ({ value: String(c.id), label: c.name ? `${c.name} (${c.email})` : c.email })))}
        {select("plan", "Plan", plans.map((p) => ({ value: String(p.id), label: `${p.name} — ${p.billing_period}` })))}
        {date("start_date", "Start date", true)}
        {date("expiry_date", "Expiry date")}
        {select("payment_term", "Payment term", terms.map((t) => ({ value: String(t.id), label: `${t.name} (${t.days} days)` })), false)}
      </div>
      <div>
        <label htmlFor="s-notes" className="mb-1 block text-sm font-medium">Notes</label>
        <textarea id="s-notes" rows={2} className={input} {...register("notes")} />
      </div>

      <div>
        <h3 className="mb-1 text-sm font-medium">Lines</h3>
        {plan && <p className="mb-2 text-xs text-slate-500">Minimum quantity for the plan's primary product: {plan.min_quantity}. Leave lines empty to start with that product.</p>}
        <div className="space-y-2">
          {fields.map((row, i) => {
            const product = products.find((p) => String(p.id) === lines[i]?.product);
            const total = lines[i] ? lineCents(lines[i]) : null;
            return (
              <div key={row.id} className="flex flex-wrap items-center gap-2 rounded border bg-slate-50 p-2">
                <select aria-label="Product" className={`${input} w-auto flex-1`} {...register(`lines.${i}.product`, { required: "Choose a product.", onChange: (e) => { setValue(`lines.${i}.variant`, ""); reprice(i, e.target.value, ""); } })}>
                  <option value="">Product…</option>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <select aria-label="Variant" className={`${input} w-auto flex-1`} {...register(`lines.${i}.variant`, { onChange: (e) => reprice(i, lines[i].product, e.target.value) })}>
                  <option value="">No variant</option>
                  {(product?.variants ?? []).map((v: any) => <option key={v.id} value={v.id}>{v.attribute}={v.value} (+{v.extra_price})</option>)}
                </select>
                <input aria-label="Quantity" type="number" min={1} className={`${input} w-20`} {...register(`lines.${i}.quantity`, { required: true, min: 1 })} />
                <input aria-label="Unit price" inputMode="decimal" className={`${input} w-28`} {...register(`lines.${i}.unit_price`, { validate: (v) => !v || MONEY.test(v) || "Enter an amount like 1000.00." })} />
                <span className="w-28 text-right text-sm" aria-label="Line total">{total === null ? "—" : <MoneyText value={centsToStr(total)} />}</span>
                <button type="button" className="rounded border px-2 py-2 text-sm text-red-700" onClick={() => remove(i)}>Remove</button>
              </div>
            );
          })}
        </div>
        <div className="mt-2 flex items-center justify-between">
          <button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => append({ product: "", variant: "", quantity: "1", unit_price: "" })}>Add line</button>
          <span className="text-sm">Subtotal (before tax): <strong><MoneyText value={centsToStr(totalCents)} /></strong></span>
        </div>
        {errors.lines && <p role="alert" className="mt-1 text-sm text-red-700">{String((errors.lines as any).message ?? "Check the lines.")}</p>}
      </div>

      <div className="flex gap-2">
        <button type="submit" disabled={isSubmitting} className="rounded bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-700 disabled:opacity-50">
          {isSubmitting ? "Please wait…" : initial ? "Save changes" : "Create draft"}
        </button>
        {onCancel && <button type="button" className="rounded border px-4 py-2" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
