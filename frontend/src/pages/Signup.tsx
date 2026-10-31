import { useState } from "react";
import { Briefcase, ShieldCheck, User as UserIcon, type LucideIcon } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import GoogleButton from "../components/GoogleButton";
import type { Field } from "../components/ResourceForm";
import ResourceForm from "../components/ResourceForm";

type Kind = "customer" | "staff" | "admin";
const KINDS: { kind: Kind; label: string; blurb: string; Icon: LucideIcon }[] = [
  { kind: "customer", label: "Customer", blurb: "Manage my subscriptions and invoices.", Icon: UserIcon },
  { kind: "staff", label: "Staff", blurb: "Run subscriptions, billing and payments. Needs a registration code.", Icon: Briefcase },
  { kind: "admin", label: "Admin", blurb: "Full access, including catalog and team. Needs a registration code.", Icon: ShieldCheck },
];

const COMMON: Field[] = [
  { name: "name", label: "Full name", autoComplete: "name" },
  { name: "email", label: "Email", type: "email", required: true, autoComplete: "email" },
  { name: "password", label: "Password", type: "password", required: true, autoComplete: "new-password", hint: "At least 9 characters with an uppercase letter, a lowercase letter and a special character." },
];
const CUSTOMER_ONLY: Field[] = [
  { name: "whatsapp_number", label: "WhatsApp number (optional)", type: "tel", placeholder: "+919876543210", hint: "10-digit Indian numbers are assumed to be +91." },
  { name: "whatsapp_opt_in", label: "Send me invoice and reminder updates on WhatsApp", type: "checkbox" },
];

export default function Signup() {
  const { signup, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [kind, setKind] = useState<Kind | null>(null);

  if (!kind) {
    return (
      <AuthShell title="How will you use Brightloop?">
        <div className="space-y-3">
          {KINDS.map(({ kind: k, label, blurb, Icon }) => (
            <button key={k} onClick={() => setKind(k)} className="flex w-full items-center gap-4 rounded-2xl border p-4 text-left transition hover:border-[var(--accent)] hover:shadow-md">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[var(--sel)]"><Icon size={20} /></span>
              <span><span className="block font-medium">{label}</span><span className="block text-sm text-slate-600">{blurb}</span></span>
            </button>
          ))}
        </div>
        <p className="mt-4 text-sm">Already registered? <Link className="text-sky-700" to="/login">Log in</Link></p>
      </AuthShell>
    );
  }

  const isCustomer = kind === "customer";
  const fields = isCustomer
    ? [...COMMON, ...CUSTOMER_ONLY]
    : [...COMMON, { name: "signup_code", label: "Registration code", type: "password", required: true, autoComplete: "off", hint: `Ask an administrator for the ${kind} registration code.` } as Field];

  return (
    <AuthShell title={`Create your ${kind} account`}>
      <button className="mb-3 text-sm text-sky-700" onClick={() => setKind(null)}>← Change account type</button>
      {isCustomer && (
        <>
          <GoogleButton label="Sign up with Google" run={() => loginWithGoogle({ account_type: "customer" }).then(() => navigate("/", { replace: true }))} />
          <p className="my-4 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />or with email<span className="h-px flex-1 bg-slate-200" /></p>
        </>
      )}
      <ResourceForm
        key={kind}
        submitLabel="Sign up"
        defaultValues={{ whatsapp_opt_in: false }}
        fields={fields}
        onSubmit={(v) => signup(isCustomer
          ? { ...v, account_type: kind, whatsapp_number: v.whatsapp_number ?? "" }
          : { name: v.name, email: v.email, password: v.password, account_type: kind, signup_code: v.signup_code })}
        successMessage="Account created. We sent a verification link to your email: open it, then log in."
      />
      <p className="mt-4 text-sm">Already registered? <Link className="text-sky-700" to="/login">Log in</Link></p>
    </AuthShell>
  );
}
