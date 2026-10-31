import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import Home from "./Home";
import MyInvoices from "./MyInvoices";
import MySubscriptions from "./MySubscriptions";

// INSIGHT (person D): home, customer portal, and later dashboard, discounts, notifications screens.
export const insightNav: NavItem[] = [
  { to: "/", label: "Home", roles: ["admin", "staff", "customer"], end: true }, // label is per-role in Layout
  { to: "/my-subscriptions", label: "My subscriptions", roles: ["customer"] },
  { to: "/my-invoices", label: "My invoices", roles: ["customer"] },
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const insightRoutes = () => [
  <Route key="home" index element={<Home />} />,
  <Route key="my-subs" path="my-subscriptions" element={<RoleGuard allow={["customer"]}><MySubscriptions /></RoleGuard>} />,
  <Route key="my-invoices" path="my-invoices" element={<RoleGuard allow={["customer"]}><MyInvoices /></RoleGuard>} />,
];
