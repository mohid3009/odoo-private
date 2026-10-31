import { Navigate, Outlet, Route } from "react-router-dom";
import Billing from "./Billing";
import InvoiceDetail from "./InvoiceDetail";
import { InvoiceList } from "./Invoices";
import InvoicePrint from "./InvoicePrint";
import Payments from "./Payments";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import { CatalogShell, PlansPage, ProductsPage, TaxesPage, TermsPage } from "./Catalog";
import Staff from "./Staff";
import SubscriptionDetail from "./SubscriptionDetail";
import { NewSubscription, SubscriptionList, SubscriptionsShell } from "./Subscriptions";
import { TemplatesPage } from "./Templates";

// OPS (people C): catalog, staff, subscriptions + templates, and later invoices, billing run, payments.
export const opsNav: NavItem[] = [
  { to: "/subscriptions", label: "Subscriptions", roles: ["admin", "staff"] },
  { to: "/invoices", label: "Invoices", roles: ["admin", "staff"] },
  { to: "/payments", label: "Payments", roles: ["admin", "staff"] },
  { to: "/billing", label: "Billing", roles: ["admin", "staff"] },
  { to: "/catalog", label: "Catalog", roles: ["admin", "staff"] },
  { to: "/staff", label: "Staff", roles: ["admin"] },
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const opsRoutes = () => [
  <Route key="subscriptions" path="subscriptions" element={<RoleGuard allow={["admin", "staff"]}><SubscriptionsShell /></RoleGuard>}>
    <Route index element={<SubscriptionList />} />
    <Route path="new" element={<NewSubscription />} />
    <Route path="templates" element={<TemplatesPage />} />
    <Route path=":id" element={<SubscriptionDetail />} />
  </Route>,
  <Route key="invoices" path="invoices" element={<RoleGuard allow={["admin", "staff"]}><Outlet /></RoleGuard>}>
    <Route index element={<InvoiceList />} />
    <Route path=":id" element={<InvoiceDetail />} />
  </Route>,
  // print is open to every role: the API only returns the caller's own invoices (customers never see drafts)
  <Route key="invoice-print" path="invoices/:id/print" element={<RoleGuard allow={["admin", "staff", "customer"]}><InvoicePrint /></RoleGuard>} />,
  <Route key="payments" path="payments" element={<RoleGuard allow={["admin", "staff"]}><Payments /></RoleGuard>} />,
  <Route key="billing" path="billing" element={<RoleGuard allow={["admin", "staff"]}><Billing /></RoleGuard>} />,
  <Route key="catalog" path="catalog" element={<RoleGuard allow={["admin", "staff"]}><CatalogShell /></RoleGuard>}>
    <Route index element={<Navigate to="products" replace />} />
    <Route path="products" element={<ProductsPage />} />
    <Route path="plans" element={<PlansPage />} />
    <Route path="taxes" element={<TaxesPage />} />
    <Route path="terms" element={<TermsPage />} />
  </Route>,
  <Route key="staff" path="staff" element={<RoleGuard allow={["admin"]}><Staff /></RoleGuard>} />,
];
