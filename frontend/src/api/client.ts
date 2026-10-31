// Money is a string end to end (D-002/rule 5): never parse it into a number for math.
import { toast } from "../components/Toast";
export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API ${status}`);
  }
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    toast("Cannot reach the server. Check your connection and try again.");
    throw e;
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data as { detail?: string } | null)?.detail;
    if (res.status >= 500) toast(detail ?? `Server error (${res.status}). Please try again.`);
    else if (res.status === 403 && detail?.startsWith("Authentication credentials") && !path.startsWith("/api/auth/"))
      toast("Your session has expired. Please log in again."); // auth pages probe /me while logged out: no toast there
    throw new ApiError(res.status, data);
  }
  return data as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T,>(path: string) => request<T>("DELETE", path),
};

export interface Health {
  status: string;
  app_db: string;
  odoo: { status: string; version?: string; error?: string };
}
