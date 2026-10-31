// Mock mode (VITE_USE_MOCK=true): answers /api/* calls in the browser from mockData.json, a snapshot of the real API
// (backend/scripts/export_mock_data.py). Reads work with filters + paging; writes are accepted but NOT saved.
// Switching to the real backend = set VITE_USE_MOCK=false. See docs/MOCK_MODE.md.
import { ApiError } from "./client";

type Row = Record<string, any>;
interface Snapshot {
  lists: Record<string, Row[]>;
  details: Record<string, Row>;
  other: Record<string, unknown>;
  users: Record<string, Row>;
  password: string;
}

let snapshot: Promise<Snapshot> | null = null;
const load = () => (snapshot ??= import("./mockData.json").then((m) => m.default as unknown as Snapshot));

const KEY = "mock-user";
const signedIn = (): string | null => { try { return localStorage.getItem(KEY); } catch { return null; } };
const remember = (email: string | null) => { try { email ? localStorage.setItem(KEY, email) : localStorage.removeItem(KEY); } catch { /* private mode */ } };
const extra: Record<string, Row> = {}; // users created by mock signup, for this tab's lifetime

const page = (rows: Row[], q: URLSearchParams) => {
  const size = Math.min(Number(q.get("page_size")) || 25, 200);
  const n = Math.max(Number(q.get("page")) || 1, 1);
  return { count: rows.length, next: null, previous: null, results: rows.slice((n - 1) * size, n * size) };
};

// Narrow a list by the query string: exact match on any field the rows have, plus the few special filters the screens use.
function filter(rows: Row[], q: URLSearchParams): Row[] {
  const skip = new Set(["page", "page_size", "ordering", "search"]);
  let out = rows;
  q.forEach((v, k) => {
    if (skip.has(k) || v === "") return;
    if (k === "overdue") out = out.filter((r) => String(!!r.is_overdue) === v);
    else if (k === "needs_attention") out = out.filter((r) => String(!!(r.payment_needs_attention ?? r.needs_attention)) === v);
    else if (rows[0] && k in rows[0]) out = out.filter((r) => String(r[k]) === v);
  });
  const s = q.get("search")?.toLowerCase();
  return s ? out.filter((r) => JSON.stringify(r).toLowerCase().includes(s)) : out;
}

const fail = (status: number, body: unknown): never => { throw new ApiError(status, body); };

export async function mockRequest<T>(method: string, path: string, body?: any): Promise<T> {
  const [snap] = await Promise.all([load(), new Promise((r) => setTimeout(r, 120))]);
  const url = new URL(path, "http://mock");
  const route = url.pathname.replace(/^\/api\//, "").replace(/\/$/, "");
  const q = url.searchParams;
  const users = { ...snap.users, ...extra };
  const me = () => (signedIn() && users[signedIn()!]) || fail(403, { detail: "Authentication credentials were not provided." });
  const ok = (v: unknown) => v as T;

  // ---- auth ----
  if (route === "auth/csrf" || route === "healthz") return ok(route === "healthz" ? snap.other.healthz : { detail: "ok" });
  if (route === "auth/login" && method === "POST") {
    const email = String(body?.email ?? "").trim().toLowerCase();
    if (!users[email] || body?.password !== snap.password) fail(400, { detail: "Invalid email or password." });
    remember(email);
    return ok(users[email]);
  }
  if (route === "auth/signup" && method === "POST") {
    const email = String(body?.email ?? "").trim().toLowerCase();
    if (users[email]) fail(400, { email: ["A user with this email already exists."] });
    const role = body?.account_type ?? "customer";
    if (role !== "customer" && body?.signup_code !== "demo") fail(400, { signup_code: ["Mock mode: use the code demo."] });
    extra[email] = { id: 1000 + Object.keys(extra).length, email, name: body?.name ?? "", role, profile: role === "customer" ? { company_name: "", phone: "", address: "", whatsapp_number: body?.whatsapp_number ?? "", whatsapp_opt_in: !!body?.whatsapp_opt_in, email_notifications: true } : null };
    return ok(extra[email]);
  }
  if (route === "auth/logout") { remember(null); return ok(null); }
  if (route === "auth/me") {
    if (method === "PATCH") {
      const u = me() as Row;
      if (body?.name !== undefined) u.name = body.name;
      if (body?.profile && u.profile) Object.assign(u.profile, body.profile);
      return ok(u);
    }
    return ok(me());
  }
  if (route.startsWith("auth/password-reset")) return ok({ detail: "If that email is registered, a reset link has been sent." });

  me(); // everything below needs a signed-in user, like the real API

  // ---- reads ----
  if (method === "GET") {
    if (route in snap.other) return ok(snap.other[route]);
    const pay = route.match(/^invoices\/(\d+)\/payments$/);
    if (pay) return ok(page(snap.lists.payments.filter((p) => String(p.invoice) === pay[1]), q));
    if (route in snap.details) return ok(snap.details[route]);
    const printM = route.match(/^invoices\/(\d+)\/print$/);
    if (printM) return ok({ ...snap.details[`invoices/${printM[1]}`], seller: { name: "Brightloop (mock)" }, customer_details: {} });
    const one = route.match(/^(.+)\/(\d+)$/);
    if (one && snap.lists[one[1]]) return ok(snap.lists[one[1]].find((r) => String(r.id) === one[2]) ?? fail(404, { detail: "Not found." }));
    if (route in snap.lists) return ok(page(filter(snap.lists[route], q), q));
    return ok(page([], q)); // an endpoint with no snapshot: empty, never a crash
  }

  // ---- writes: accepted, not saved ----
  console.info(`[mock] ${method} ${path} was accepted but not saved`);
  const inv = route.match(/^invoices\/(\d+)\//);
  if (inv && snap.details[`invoices/${inv[1]}`]) return ok(snap.details[`invoices/${inv[1]}`]);
  if (route === "notifications/test-send") return ok({ ok: true, provider: "console", detail: "mock" });
  if (route === "notifications/run-reminders") return ok({ as_of: new Date().toLocaleDateString("en-CA"), due_soon: 0, overdue: 0, expiring: 0 });
  if (route === "billing/run") return ok({ run_id: 0, created: 0, skipped: 0, errors: 0 });
  return ok({ ...(body ?? {}), id: Date.now() });
}
