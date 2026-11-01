import { useState } from "react";
import { Briefcase, ShieldCheck, User as UserIcon, type LucideIcon } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { AuthShell } from "../components/Layout";
import CodeSlots from "../components/CodeSlots";
import GoogleButton from "../components/GoogleButton";
import type { Field } from "../components/ResourceForm";
import ResourceForm from "../components/ResourceForm";

// demo build: the registration codes are shown on the page. Set VITE_SHOW_DEMO=false on the host to hide them.
const SHOW_DEMO = import.meta.env.VITE_SHOW_DEMO !== "false";

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
  const [code, setCode] = useState("");
  const [codeStatus, setCodeStatus] = useState<"idle" | "success" | "error">("idle");

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

  const meta = KINDS.find((k) => k.kind === kind)!;
  const isCustomer = kind === "customer";
  const fields = isCustomer ? [...COMMON, ...CUSTOMER_ONLY] : COMMON;
  // staff/admin: one registration code, shared by the email form and the Google button (the server checks it, D-044)
  const needCode = () => {
    if (!isCustomer && code.length < 6) throw new ApiError(400, { detail: `Enter the 6-digit ${kind} registration code first.` });
  };
  const extra = isCustomer ? { account_type: kind } : { account_type: kind, signup_code: code };
  // the sixth digit triggers a server check; CodeSlots plays the success wash or the error drain (sign-up re-checks it anyway)
  const verify = async (c: string) => {
    try {
      const r = await api.post<{ valid: boolean }>("/api/auth/check-code/", { account_type: kind, code: c });
      setCodeStatus(r.valid ? "success" : "error");
    } catch {
      setCodeStatus("error");
    }
  };

  return (
    <AuthShell title={`Create your ${kind} account`}>
      {/* which account type this form creates, unmissable at the top */}
      <div className="mb-4 flex items-center gap-3 rounded-xl border bg-[var(--sel)] p-3" role="status">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white text-sky-700 shadow-sm"><meta.Icon size={18} /></span>
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-slate-500">You are creating a</p>
          <p className="font-semibold">{meta.label} account</p>
          <p className="text-xs text-slate-500">{meta.blurb}</p>
        </div>
      </div>
      <button className="mb-3 text-sm text-sky-700" onClick={() => { setKind(null); setCode(""); setCodeStatus("idle"); }}>← Change account type</button>
      {!isCustomer && (
        <div className="mb-4 text-sm">
          <span className="mb-2 block font-medium">Registration code</span>
          <CodeSlots
            key={kind} length={6} status={codeStatus} onComplete={verify} onChange={(c) => { setCode(c); setCodeStatus("idle"); }} ariaLabel={`${kind} registration code`}
            slotColor="#eef2f7" inkColor="#0f172a" accentColor="#0a84ff" digitColor="#ffffff" slotSize={42} gap={8}
          />
          <span className="mt-2 block text-xs text-slate-500">Ask an administrator for the {kind} registration code. It applies to both options below.</span>
          {SHOW_DEMO && <span className="mt-1 block text-xs text-slate-500">Demo codes: staff <strong className="font-mono">246813</strong> · admin <strong className="font-mono">123456</strong></span>}
        </div>
      )}
      <ResourceForm
        key={kind}
        submitLabel="Sign up with email"
        defaultValues={{ whatsapp_opt_in: false }}
        fields={fields}
        onSubmit={(v) => {
          needCode();
          return signup(isCustomer ? { ...v, ...extra, whatsapp_number: v.whatsapp_number ?? "" } : { name: v.name, email: v.email, password: v.password, ...extra });
        }}
        successMessage="Account created. We sent a verification link to your email: open it, then log in."
      />
      <p className="my-4 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />or<span className="h-px flex-1 bg-slate-200" /></p>
      <GoogleButton label={`Sign up as ${kind} with Google`} run={async () => { needCode(); await loginWithGoogle(extra); navigate("/", { replace: true }); }} />
      <p className="mt-4 text-sm">Already registered? <Link className="text-sky-700" to="/login">Log in</Link></p>
    </AuthShell>
  );
}
