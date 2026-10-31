import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import Dashboard from "./Dashboard";
import { DiscountsPage } from "./Discounts";
import DiscountRedemptions from "./DiscountRedemptions";
import Home from "./Home";
import MyInvoices from "./MyInvoices";
import MyNotifications from "./MyNotifications";
import MySubscriptionDetail from "./MySubscriptionDetail";
import MySubscriptions from "./MySubscriptions";
import PaymentHistory from "./PaymentHistory";

// INSIGHT (person D): home, finance dashboard, discounts, customer portal.
export const insightNav: NavItem[] = [
  { to: "/", label: "Home", roles: ["admin", "staff", "customer"], end: true }, // label is per-role in Layout
  { to: "/dashboard", label: "Dashboard", roles: ["admin", "staff"] },
  { to: "/discounts", label: "Discounts", roles: ["admin", "staff"] },
  { to: "/my-subscriptions", label: "My subscriptions", roles: ["customer"] },
  { to: "/my-invoices", label: "My invoices", roles: ["customer"] },
  { to: "/my-payments", label: "Payments", roles: ["customer"] },
  { to: "/my-notifications", label: "Notifications", roles: ["customer"] },
];

const customer = ["customer"] as const;
const internal = ["admin", "staff"] as const;

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
// Customer pages live under /my-*: ops owns /payments etc. for staff, and two routes on one path shadow each other.
export const insightRoutes = () => [
  <Route key="home" index element={<Home />} />,
  <Route key="dashboard" path="dashboard" element={<RoleGuard allow={[...internal]}><Dashboard /></RoleGuard>} />,
  <Route key="discounts" path="discounts" element={<RoleGuard allow={[...internal]}><DiscountsPage /></RoleGuard>} />,
  <Route key="discount-redemptions" path="discounts/:id/redemptions" element={<RoleGuard allow={[...internal]}><DiscountRedemptions /></RoleGuard>} />,
  <Route key="my-subs" path="my-subscriptions" element={<RoleGuard allow={[...customer]}><MySubscriptions /></RoleGuard>} />,
  <Route key="my-sub" path="my-subscriptions/:id" element={<RoleGuard allow={[...customer]}><MySubscriptionDetail /></RoleGuard>} />,
  <Route key="my-invoices" path="my-invoices" element={<RoleGuard allow={[...customer]}><MyInvoices /></RoleGuard>} />,
  <Route key="my-payments" path="my-payments" element={<RoleGuard allow={[...customer]}><PaymentHistory /></RoleGuard>} />,
  <Route key="my-notifs" path="my-notifications" element={<RoleGuard allow={[...customer]}><MyNotifications /></RoleGuard>} />,
];
