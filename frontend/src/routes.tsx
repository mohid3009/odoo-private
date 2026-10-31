import { AnimatePresence, motion } from "framer-motion";
import { Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import RoleGuard from "./components/RoleGuard";
import { insightRoutes } from "./features/insight/routes";
import { opsRoutes } from "./features/ops/routes";
import BrightloopIntro from "./pages/BrightloopIntro";
import ForgotPassword from "./pages/ForgotPassword";
import Forbidden from "./pages/Forbidden";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import NotFound from "./pages/NotFound";
import Profile from "./pages/Profile";
import Signup from "./pages/Signup";

// Shared shell + auth pages live here and in pages/. Feature screens are added in
// features/ops/routes.tsx and features/insight/routes.tsx, not in this file (see docs/TEAM.md).
const PUBLIC = ["/welcome", "/login", "/signup", "/forgot-password"];

// Fade/slide between public pages; everything behind the shell shares one key so its own animations run untouched.
const Fade = ({ children }: { children: JSX.Element }) => (
  <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.25 }}>
    {children}
  </motion.div>
);

export default function AppRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
    <Routes location={location} key={PUBLIC.includes(location.pathname) ? location.pathname : "app"}>
      <Route path="/welcome" element={<Fade><BrightloopIntro /></Fade>} />
      <Route path="/login" element={<Fade><Login /></Fade>} />
      <Route path="/signup" element={<Fade><Signup /></Fade>} />
      <Route path="/forgot-password" element={<Fade><ForgotPassword /></Fade>} />
      <Route path="/status" element={<Landing />} />
      <Route element={<RoleGuard><Layout /></RoleGuard>}>
        {insightRoutes()}
        {opsRoutes()}
        <Route path="profile" element={<Profile />} />
        <Route path="403" element={<Forbidden />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </AnimatePresence>
  );
}
