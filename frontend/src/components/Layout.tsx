import { ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import type { Role } from "../api/types";
import { insightNav } from "../features/insight/routes";
import { opsNav } from "../features/ops/routes";
import type { NavItem } from "./nav";

// Each feature folder owns its nav entries; a role only sees what it may open.
const NAV: NavItem[] = [
  ...insightNav,
  ...opsNav,
  { to: "/profile", label: "Profile", roles: ["admin", "staff", "customer"] },
];

const HOME_LABEL: Record<Role, string> = { admin: "Admin home", staff: "Staff home", customer: "My account" };

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  return (
    <div className="min-h-screen">
      <header className="no-print border-b bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-semibold">Brightloop</span>
          <nav className="flex flex-wrap gap-4 text-sm">
            {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "font-semibold text-indigo-700" : "text-slate-600 hover:text-slate-900")}>
                {n.to === "/" ? HOME_LABEL[user.role] : n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">{user.email}</span>
            <span className="rounded bg-slate-100 px-2 py-0.5 capitalize">{user.role}</span>
            <button className="rounded border px-3 py-1 hover:bg-slate-50" onClick={async () => { await logout(); navigate("/login"); }}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <h1 className="mb-1 text-2xl font-semibold">Brightloop</h1>
      <h2 className="mb-5 text-slate-600">{title}</h2>
      <div className="rounded border bg-white p-5">{children}</div>
    </div>
  );
}
