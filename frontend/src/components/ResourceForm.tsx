import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFieldArray, useForm, UseFormReturn } from "react-hook-form";
import { api, ApiError } from "../api/client";
import type { Page } from "../api/types";

export type FieldType =
  | "text" | "email" | "password" | "tel" | "number" | "money" | "date"
  | "textarea" | "select" | "checkbox" | "multiselect" | "lines";

export interface OptionsFrom {
  endpoint: string;
  label: (row: any) => string;
  expand?: (rows: any[]) => { value: string; label: string }[]; // one row -> many options (e.g. product variants)
}

export interface Field {
  name: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[];
  optionsFrom?: OptionsFrom; // select / multiselect options loaded from a list endpoint
  lineFields?: Field[]; // for type "lines": sub-fields of each row (carry the row id in a hidden `_id`)
  addLabel?: string;
  hint?: string;
  placeholder?: string;
  autoComplete?: string;
  validate?: (value: any, all: Record<string, any>) => string | true;
}

interface Props {
  fields: Field[];
  submitLabel: string;
  onSubmit: (values: Record<string, any>) => Promise<unknown>;
  defaultValues?: Record<string, any>;
  onSuccess?: () => void;
  onCancel?: () => void;
  successMessage?: string;
  resetOnSuccess?: boolean;
}

type Form = UseFormReturn<Record<string, any>>;

const input = "w-full rounded border border-slate-300 px-3 py-2 focus:border-indigo-500 focus:outline-none";
const MONEY = /^-?\d+(\.\d{1,2})?$/;

// DRF error bodies: {field: [msg]}, {detail: msg}, or nested {profile: {field: [msg]}} -> flat {field: msg}
export function flatten(body: unknown, out: Record<string, string> = {}): Record<string, string> {
  if (body && typeof body === "object") {
    for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
      if (Array.isArray(v)) out[k] = v.map((x) => (typeof x === "object" ? Object.values(x as object).flat().join(" ") : String(x))).join(" ");
      else if (typeof v === "string") out[k] = v;
      else flatten(v, out);
    }
  }
  return out;
}

function useOptions(f: Field) {
  const q = useQuery({
    queryKey: ["options", f.optionsFrom?.endpoint],
    enabled: !!f.optionsFrom,
    queryFn: () => api.get<Page<any>>(`${f.optionsFrom!.endpoint}?page_size=200`),
  });
  if (!f.optionsFrom) return f.options ?? [];
  const rows = q.data?.results ?? [];
  if (f.optionsFrom.expand) return f.optionsFrom.expand(rows);
  return rows.map((r) => ({ value: String(r.id), label: f.optionsFrom!.label(r) }));
}

// A select inside a `lines` row (its own component because useOptions is a hook).
function LineSelect({ f, form, name }: { f: Field; form: Form; name: string }) {
  const options = useOptions(f);
  return (
    <select aria-label={f.label} className={`${input} w-auto min-w-0 flex-1`} {...form.register(name, rules(f, form))}>
      <option value="">{f.placeholder ?? (f.required ? "Select…" : "—")}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function rules(f: Field, form: Form) {
  return {
    required: f.required && f.type !== "checkbox" ? `${f.label} is required.` : false,
    validate: (v: any) => {
      if (f.type === "money" && v !== "" && v != null && !MONEY.test(String(v))) return "Enter an amount like 1000.00.";
      return f.validate ? f.validate(v, form.getValues()) : true;
    },
  };
}

function ScalarControl({ f, form, id, name }: { f: Field; form: Form; id: string; name: string }) {
  const options = useOptions(f);
  const reg = form.register(name, rules(f, form));
  if (f.type === "textarea") return <textarea id={id} rows={3} className={input} {...reg} />;
  if (f.type === "select")
    return (
      <select id={id} className={input} {...reg}>
        {(f.optionsFrom || f.placeholder) && <option value="">{f.placeholder ?? "Select…"}</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  if (f.type === "checkbox") return <input id={id} type="checkbox" className="mr-2" {...form.register(name)} />;
  const type = f.type === "money" ? "text" : f.type === "number" ? "number" : f.type ?? "text";
  return (
    <input id={id} type={type} inputMode={f.type === "money" ? "decimal" : undefined} min={f.type === "number" ? 0 : undefined}
      placeholder={f.placeholder} autoComplete={f.autoComplete} className={input} {...reg} />
  );
}

function MultiSelect({ f, form }: { f: Field; form: Form }) {
  const options = useOptions(f);
  form.register(f.name);
  const value: string[] = (form.watch(f.name) ?? []).map(String);
  const toggle = (v: string) =>
    form.setValue(f.name, value.includes(v) ? value.filter((x) => x !== v) : [...value, v], { shouldDirty: true });
  if (options.length === 0) return <p className="text-sm text-slate-500">None available yet.</p>;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      {options.map((o) => (
        <label key={o.value} className="flex items-center text-sm">
          <input type="checkbox" className="mr-2" checked={value.includes(o.value)} onChange={() => toggle(o.value)} />
          {o.label}
        </label>
      ))}
    </div>
  );
}

function Lines({ f, form }: { f: Field; form: Form }) {
  const { fields, append, remove } = useFieldArray({ control: form.control, name: f.name });
  const subs = f.lineFields ?? [];
  return (
    <div className="space-y-2">
      {fields.map((row, i) => (
        <div key={row.id} className="flex flex-wrap items-start gap-2 rounded border bg-slate-50 p-2">
          <input type="hidden" {...form.register(`${f.name}.${i}._id`)} />
          {subs.map((s) => s.type === "select" ? (
            <LineSelect key={s.name} f={s} form={form} name={`${f.name}.${i}.${s.name}`} />
          ) : (
            <input key={s.name} aria-label={s.label} placeholder={s.label} inputMode={s.type === "money" ? "decimal" : undefined}
              className={`${input} w-auto min-w-0 flex-1`} {...form.register(`${f.name}.${i}.${s.name}`, rules(s, form))} />
          ))}
          <button type="button" className="rounded border px-2 py-2 text-sm text-red-700" onClick={() => remove(i)}>Remove</button>
        </div>
      ))}
      <button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => append(Object.fromEntries([["_id", ""], ...subs.map((s) => [s.name, ""])]))}>
        {f.addLabel ?? "Add row"}
      </button>
    </div>
  );
}

export default function ResourceForm({ fields, submitLabel, onSubmit, defaultValues, onSuccess, onCancel, successMessage, resetOnSuccess }: Props) {
  const form = useForm<Record<string, any>>({ defaultValues });
  const { handleSubmit, setError, clearErrors, reset, formState } = form;
  const { errors, isSubmitting } = formState;
  const [done, setDone] = useState(false);

  const submit = handleSubmit(async (values) => {
    setDone(false);
    const body = { ...values };
    for (const f of fields) if (f.type === "date" && body[f.name] === "") body[f.name] = null; // blank date -> null
    try {
      await onSubmit(body);
      setDone(true);
      if (resetOnSuccess) reset(defaultValues);
      onSuccess?.();
    } catch (e) {
      if (e instanceof ApiError && e.body && typeof e.body === "object") {
        const flat = flatten(e.body);
        let placed = false;
        for (const [k, msg] of Object.entries(flat)) {
          if (fields.some((f) => f.name === k)) { setError(k, { message: msg }); placed = true; }
        }
        const rest = Object.entries(flat).filter(([k]) => !fields.some((f) => f.name === k)).map(([, m]) => m);
        if (rest.length || !placed) setError("root.server", { message: rest.join(" ") || `Request failed (${e.status})` });
      } else {
        setError("root.server", { message: "Network error. Please try again." });
      }
    }
  });

  return (
    // clearErrors first: a server error set with setError on a rule-less field (e.g. a `lines` list) would otherwise block every resubmit
    <form onSubmit={(e) => { clearErrors(); return submit(e); }} className="space-y-4" noValidate>
      {errors.root?.server && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{errors.root.server.message}</p>}
      {done && successMessage && <p role="status" className="rounded bg-green-50 px-3 py-2 text-sm text-green-800">{successMessage}</p>}
      {fields.map((f) => {
        const err = errors[f.name]?.message as string | undefined;
        const id = `f-${f.name}`;
        return (
          <div key={f.name}>
            {f.type === "checkbox" ? (
              <label htmlFor={id} className="flex items-start text-sm"><ScalarControl f={f} form={form} id={id} name={f.name} /><span>{f.label}</span></label>
            ) : (
              <>
                <label htmlFor={id} className="mb-1 block text-sm font-medium">{f.label}{f.required && " *"}</label>
                {f.type === "multiselect" ? <MultiSelect f={f} form={form} />
                  : f.type === "lines" ? <Lines f={f} form={form} />
                  : <ScalarControl f={f} form={form} id={id} name={f.name} />}
              </>
            )}
            {f.hint && !err && <p className="mt-1 text-xs text-slate-500">{f.hint}</p>}
            {err && <p role="alert" className="mt-1 text-sm text-red-700">{err}</p>}
          </div>
        );
      })}
      <div className="flex gap-2">
        <button type="submit" disabled={isSubmitting} className="rounded bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
          {isSubmitting ? "Please wait…" : submitLabel}
        </button>
        {onCancel && <button type="button" className="rounded border px-4 py-2" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
