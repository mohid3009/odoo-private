import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import { DiscountsPage } from "./Discounts";
import DiscountRedemptions from "./DiscountRedemptions";
import Home from "./Home";
import MyInvoices from "./MyInvoices";
import MySubscriptions from "./MySubscriptions";
import PaymentHistory from "./PaymentHistory";

// INSIGHT (person D): home, discounts, customer portal.
export const insightNav: NavItem[] = [
  { to: "/", label: "Home", roles: ["admin", "staff", "customer"], end: true }, // label is per-role in Layout
  { to: "/discounts", label: "Discounts", roles: ["admin", "staff"] },
  { to: "/my-subscriptions", label: "My subscriptions", roles: ["customer"] },
  { to: "/my-invoices", label: "My invoices", roles: ["customer"] },
  { to: "/payments", label: "Payments", roles: ["customer"] },
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const insightRoutes = () => [
  <Route key="home" index element={<Home />} />,
  <Route key="discounts" path="discounts" element={<RoleGuard allow={["admin", "staff"]}><DiscountsPage /></RoleGuard>} />,
  <Route key="discount-redemptions" path="discounts/:id/redemptions" element={<RoleGuard allow={["admin", "staff"]}><DiscountRedemptions /></RoleGuard>} />,
  <Route key="my-subs" path="my-subscriptions" element={<RoleGuard allow={["customer"]}><MySubscriptions /></RoleGuard>} />,
  <Route key="my-invoices" path="my-invoices" element={<RoleGuard allow={["customer"]}><MyInvoices /></RoleGuard>} />,
  <Route key="payments" path="payments" element={<RoleGuard allow={["customer"]}><PaymentHistory /></RoleGuard>} />,
];
