import { Navigate, Route, Routes } from "react-router-dom";
import { CatalogShell, PlansPage, ProductsPage, TaxesPage, TermsPage } from "./pages/Catalog";
import Layout from "./components/Layout";
import RoleGuard from "./components/RoleGuard";
import ForgotPassword from "./pages/ForgotPassword";
import Forbidden from "./pages/Forbidden";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Profile from "./pages/Profile";
import ResetPassword from "./pages/ResetPassword";
import Signup from "./pages/Signup";
import Staff from "./pages/Staff";

// Route map grows per phase; see docs/FRONTEND.md.
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
      <Route path="/status" element={<Landing />} />
      <Route element={<RoleGuard><Layout /></RoleGuard>}>
        <Route index element={<Home />} />
        <Route path="profile" element={<Profile />} />
        <Route path="staff" element={<RoleGuard allow={["admin"]}><Staff /></RoleGuard>} />
        <Route path="catalog" element={<RoleGuard allow={["admin", "staff"]}><CatalogShell /></RoleGuard>}>
          <Route index element={<Navigate to="products" replace />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="taxes" element={<TaxesPage />} />
          <Route path="terms" element={<TermsPage />} />
        </Route>
        <Route path="403" element={<Forbidden />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
