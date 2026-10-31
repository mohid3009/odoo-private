import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import { DiscountsPage } from "./Discounts";
import DiscountRedemptions from "./DiscountRedemptions";
import Home from "./Home";

// INSIGHT (person D): home, discounts, and later dashboard, customer portal, notifications screens.
export const insightNav: NavItem[] = [
  { to: "/", label: "Home", roles: ["admin", "staff", "customer"], end: true }, // label is per-role in Layout
  { to: "/discounts", label: "Discounts", roles: ["admin", "staff"] },
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const insightRoutes = () => [
  <Route key="home" index element={<Home />} />,
  <Route key="discounts" path="discounts" element={<RoleGuard allow={["admin", "staff"]}><DiscountsPage /></RoleGuard>} />,
  <Route key="discount-redemptions" path="discounts/:id/redemptions" element={<RoleGuard allow={["admin", "staff"]}><DiscountRedemptions /></RoleGuard>} />,
];
