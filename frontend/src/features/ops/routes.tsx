import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import Staff from "./Staff";

// OPS (person C): staff, and later subscriptions, invoices, billing run, payments.
export const opsNav: NavItem[] = [{ to: "/staff", label: "Staff", roles: ["admin"] }];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const opsRoutes = () => [
  <Route key="staff" path="staff" element={<RoleGuard allow={["admin"]}><Staff /></RoleGuard>} />,
];
