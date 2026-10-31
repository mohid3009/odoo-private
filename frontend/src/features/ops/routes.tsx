import { Navigate, Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import { CatalogShell, PlansPage, ProductsPage, TaxesPage, TermsPage } from "./Catalog";
import Staff from "./Staff";

// OPS (people C): catalog, staff, and later subscriptions, invoices, billing run, payments.
export const opsNav: NavItem[] = [
  { to: "/catalog", label: "Catalog", roles: ["admin", "staff"] },
  { to: "/staff", label: "Staff", roles: ["admin"] },
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const opsRoutes = () => [
  <Route key="catalog" path="catalog" element={<RoleGuard allow={["admin", "staff"]}><CatalogShell /></RoleGuard>}>
    <Route index element={<Navigate to="products" replace />} />
    <Route path="products" element={<ProductsPage />} />
    <Route path="plans" element={<PlansPage />} />
    <Route path="taxes" element={<TaxesPage />} />
    <Route path="terms" element={<TermsPage />} />
  </Route>,
  <Route key="staff" path="staff" element={<RoleGuard allow={["admin"]}><Staff /></RoleGuard>} />,
];
