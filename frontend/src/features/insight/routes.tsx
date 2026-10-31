import { Route } from "react-router-dom";
import type { NavItem } from "../../components/nav";
import Home from "./Home";

// INSIGHT (person D): home, and later dashboard, customer portal, discounts, notifications screens.
export const insightNav: NavItem[] = [
  { to: "/", label: "Home", roles: ["admin", "staff", "customer"], end: true }, // label is per-role in Layout
];

// Called (not rendered) inside <Routes> in src/routes.tsx, so each element needs a key.
export const insightRoutes = () => [<Route key="home" index element={<Home />} />];
