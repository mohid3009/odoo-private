import PageLoader from "./PageLoader";
import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import type { Role } from "../api/types";

// Cosmetic only (rule 8): the server enforces every permission. Without `fallback` it redirects.
export default function RoleGuard({ allow, children, fallback }: { allow?: Role[]; children: ReactNode; fallback?: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoader />;
  // a logged-out visitor on the bare site URL gets the landing page; deep links still go to the login form
  if (!user) return fallback !== undefined ? <>{fallback}</> : <Navigate to={location.pathname === "/" ? "/welcome" : "/login"} replace state={{ from: location.pathname }} />;
  if (allow && !allow.includes(user.role)) return fallback !== undefined ? <>{fallback}</> : <Navigate to="/403" replace />;
  return <>{children}</>;
}
