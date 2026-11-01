import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import RoleGuard from "../../components/RoleGuard";
import { MyInvoiceDetail, MyInvoices, MyPayments, MySubscriptions, PayInvoice } from "./Customer";

// CUSTOMER self-service: own subscriptions, invoices, online payment and payment history.
// Staff/admin keep their own screens at /subscriptions, /invoices, /payments; these live under /my so the paths never clash.
export const customerNav: NavItem[] = [
  { to: "/my/subscriptions", label: "My subscriptions", roles: ["customer"] },
  { to: "/my/invoices", label: "My invoices", roles: ["customer"] },
  { to: "/my/payments", label: "Payment history", roles: ["customer"] },
];

const only = (el: JSX.Element) => <RoleGuard allow={["customer"]}>{el}</RoleGuard>;

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const customerRoutes = () => [
  <Route key="my-subscriptions" path="my/subscriptions" element={only(<MySubscriptions />)} />,
  <Route key="my-invoices" path="my/invoices" element={only(<MyInvoices />)} />,
  <Route key="my-invoice" path="my/invoices/:id" element={only(<MyInvoiceDetail />)} />,
  <Route key="my-pay" path="my/pay/:id" element={only(<PayInvoice />)} />,
  <Route key="my-payments" path="my/payments" element={only(<MyPayments />)} />,
];
