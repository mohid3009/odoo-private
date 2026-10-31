import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RoleGuard from "./components/RoleGuard";
import { insightRoutes } from "./features/insight/routes";
import { opsRoutes } from "./features/ops/routes";
import ForgotPassword from "./pages/ForgotPassword";
import Forbidden from "./pages/Forbidden";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Profile from "./pages/Profile";
import ResetPassword from "./pages/ResetPassword";
import Signup from "./pages/Signup";

// Shared shell + auth pages live here and in pages/. Feature screens are added in
// features/ops/routes.tsx and features/insight/routes.tsx, not in this file (see docs/TEAM.md).
export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
      <Route path="/status" element={<Landing />} />
      <Route element={<RoleGuard><Layout /></RoleGuard>}>
        {insightRoutes()}
        {opsRoutes()}
        <Route path="profile" element={<Profile />} />
        <Route path="403" element={<Forbidden />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
