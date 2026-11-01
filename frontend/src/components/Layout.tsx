import { AnimatePresence, LayoutGroup, motion, MotionConfig } from "framer-motion";
import {
  Bell, ChevronsLeft, ChevronsRight, CircleDot, CreditCard, FileText, LayoutDashboard, LogOut, Moon, Package, Percent, Repeat, Search,
  Sun, UserCircle, Users, Zap, type LucideIcon,
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import type { Role } from "../api/types";
import { customerNav } from "../features/customer/routes";
import { insightNav } from "../features/insight/routes";
import { opsNav } from "../features/ops/routes";
import { useTheme, ThemeProvider } from "../lib/theme";
import CommandPalette, { type Cmd } from "./layout/CommandPalette";
import type { NavItem } from "./nav";
import { EASE, Glass, ToastProvider, useToast } from "./ui/glass";
import Grainient from "./ui/Grainient";

// Each feature folder owns its nav entries; a role only sees what it may open.
const NAV: NavItem[] = [
  ...insightNav,
  ...opsNav,
  ...customerNav,
  { to: "/profile", label: "Profile", roles: ["admin", "staff", "customer"] },
];

const HOME_LABEL: Record<Role, string> = { admin: "Dashboard", staff: "Dashboard", customer: "My account" };
const ICONS: Record<string, LucideIcon> = {
  "/": LayoutDashboard, "/discounts": Percent, "/subscriptions": Repeat, "/invoices": FileText, "/payments": CreditCard,
  "/billing": Zap, "/catalog": Package, "/notifications": Bell, "/staff": Users, "/profile": UserCircle,
  "/my/subscriptions": Repeat, "/my/invoices": FileText, "/my/payments": CreditCard,
};

// First colour = page background (#f5f5f7 light, #000 dark) so the edges blend into the UI.
const BG_LIGHT = ["#f5f5f7", "#e9eaf0", "#d8dff0", "#bccbe9", "#9db4e0"];
const BG_DARK = ["#000000", "#0b0b10", "#12162b", "#1b2b5e", "#4f6fd6"];

function Backdrop() {
  const { theme } = useTheme();
  return (
    <div aria-hidden className="no-print pointer-events-none fixed inset-0 -z-10">
      <Grainient colors={theme === "dark" ? BG_DARK : BG_LIGHT} angle={55} flow={1.4} silk={0.45} speed={2.4} grainAmount={0.06} saturation={1.25} />
    </div>
  );
}

function ThemeButton() {
  const { theme, toggle } = useTheme();
  const toast = useToast();
  return (
    <button
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      onClick={() => { toggle(); toast(`Switched to ${theme === "dark" ? "light" : "dark"} theme`); }}
      className="tap grid h-12 w-12 shrink-0 place-items-center rounded-full text-fg2 transition-all hover:scale-105 hover:text-fg"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={theme} initial={{ rotate: -60, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 60, opacity: 0 }} transition={{ duration: 0.18 }}>
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

function Shell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { toggle } = useTheme();
  const toast = useToast();
  const [palette, setPalette] = useState(false);
  const [menu, setMenu] = useState(false);
  // Expanded the first time the app opens; after that the visitor's own choice sticks. (New key: an old "collapsed" value from the
  // earlier default must not keep hiding the labels.)
  const [expanded, setExpanded] = useState(() => { try { return localStorage.getItem("rail-expanded-v2") !== "0"; } catch { return true; } });
  const toggleExpanded = () => setExpanded((e) => { try { localStorage.setItem("rail-expanded-v2", e ? "0" : "1"); } catch { /* private mode */ } return !e; });

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
      if (e.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  const items = useMemo(
    () => (user ? NAV.filter((n) => n.roles.includes(user.role)).map((n) => ({ ...n, label: n.to === "/" ? HOME_LABEL[user.role] : n.label, Icon: ICONS[n.to] ?? CircleDot })) : []),
    [user],
  );
  if (!user) return null;

  const doLogout = async () => { await logout(); navigate("/welcome"); };
  const cmds: Cmd[] = [
    ...items.map((n) => ({ label: `Go to ${n.label}`, Icon: n.Icon, run: () => navigate(n.to) })),
    { label: "Toggle theme", Icon: Sun, run: toggle },
    { label: "Log out", Icon: LogOut, run: doLogout },
  ];
  const initial = (user.name || user.email).charAt(0).toUpperCase();
  const avatar = <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-b from-[#409cff] to-[#0071e3] font-semibold text-white">{initial}</span>;
  const first = (user.name || user.email.split("@")[0]).split(" ")[0];
  const here = items.find((n) => (n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)))?.label;
  // one row style for every rail button: a 48px circle when collapsed, a full-width pill with a label when expanded
  const row = `tap relative shrink-0 rounded-full ${expanded ? "flex w-full items-center gap-3 px-3.5" : "grid w-12 place-items-center"}`;

  return (
    // md+: a fixed-height shell. The header and the rail never scroll; only the content column does. Phones keep the normal page flow.
    <div className="min-h-screen md:h-screen md:overflow-hidden">
      <Backdrop />
      <div className="mx-auto flex max-w-[1500px] flex-col px-4 pb-28 pt-5 md:h-full md:px-8 md:pb-6 md:pt-8">
        {/* Greeting row: brand mark, hello + where you are, then search and round glass buttons */}
        <header className="no-print flex flex-wrap items-center gap-x-4 gap-y-3 md:shrink-0">
          <Link to="/" aria-label="Brightloop home" className="grid h-14 w-14 shrink-0 place-items-center rounded-full text-accent"><Repeat size={34} strokeWidth={2.2} /></Link>
          <div className="min-w-0 flex-1 basis-56">
            <h1 className="truncate text-2xl font-medium tracking-tight sm:text-[28px]">Hello, {first}!</h1>
            <p className="truncate text-sm text-fg2">{here && here !== HOME_LABEL[user.role] ? `You are viewing ${here}` : "Explore information and activity about your subscriptions"}</p>
          </div>
          <Glass flat className="flex w-full items-center gap-2 !rounded-full p-1.5 sm:w-auto sm:min-w-[300px] lg:min-w-[380px]">
            <button onClick={() => setPalette(true)} className="tap flex min-w-0 flex-1 items-center gap-2 rounded-full px-4 text-left text-sm text-muted">
              <span className="truncate">Search…</span><kbd className="ml-auto hidden rounded-md border border-[var(--glass-border)] px-1.5 py-0.5 text-[10px] sm:block">⌘K</kbd>
            </button>
            <button aria-label="Search pages and actions" onClick={() => setPalette(true)} className="tap grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--fg)] text-[var(--bg)]"><Search size={17} /></button>
          </Glass>
          <Glass flat className="!rounded-full"><ThemeButton /></Glass>
          <Glass flat className="!rounded-full">
            <button aria-label="Notifications" onClick={() => toast("You're all caught up")} className="tap relative grid h-12 w-12 place-items-center rounded-full text-fg2 hover:text-fg">
              <Bell size={19} />
              <span className="absolute right-3 top-3 flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#FF453A] opacity-70" /><span className="relative inline-flex h-2 w-2 rounded-full bg-[#FF453A]" /></span>
            </button>
          </Glass>
          <div className="relative">
            <button aria-label="Profile menu" aria-expanded={menu} onClick={() => setMenu((m) => !m)} className="tap rounded-full">{avatar}</button>
            <AnimatePresence>
              {menu && (
                <>
                  <button aria-hidden tabIndex={-1} className="fixed inset-0 z-40 cursor-default" onClick={() => setMenu(false)} />
                  <motion.div initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="tip absolute right-0 top-full z-50 mt-2 w-56 p-2 text-sm">
                    <p className="truncate px-3 py-2 text-xs text-fg2">{user.email}</p>
                    <Link to="/profile" onClick={() => setMenu(false)} className="tap flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-[var(--sel)]"><UserCircle size={16} />Profile</Link>
                    <button onClick={doLogout} className="tap flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left hover:bg-[var(--sel)]"><LogOut size={16} />Log out</button>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </header>

        <div className="mt-6 flex items-start gap-5 md:min-h-0 md:flex-1 md:items-stretch md:gap-6">
          {/* Floating icon rail (md+): one glass pill pinned to the shell height; the active item is a filled circle that slides */}
          <motion.aside animate={{ width: expanded ? 232 : 76 }} transition={{ duration: 0.28, ease: EASE }} className="no-print hidden shrink-0 overscroll-contain md:block md:h-full">
            <Glass flat className={`flex h-full flex-col overflow-hidden p-3 ${expanded ? "!rounded-[36px]" : "items-center !rounded-full"}`}>
              <button aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"} aria-expanded={expanded} title={expanded ? "Collapse" : "Expand"} onClick={toggleExpanded} className={`${row} mb-1 h-12 text-fg2 hover:bg-[var(--sel)] hover:text-fg`}>
                {expanded ? <ChevronsLeft size={19} /> : <ChevronsRight size={19} />}
                {expanded && <span className="truncate text-sm font-medium">Collapse</span>}
              </button>
              {/* No scrolling: when the window is short the items compress (flex-1, 36-48px) instead of overflowing */}
              <nav aria-label="Main" className={`flex min-h-0 flex-1 flex-col gap-1 overflow-hidden ${expanded ? "" : "items-center"}`}>
                <LayoutGroup id="nav">
                  {items.map((n) => (
                    <NavLink key={n.to} to={n.to} end={n.end} title={expanded ? undefined : n.label} aria-label={n.label} className={({ isActive }) => `${row} min-h-9 max-h-12 flex-1 transition-colors ${isActive ? "text-[var(--bg)]" : "text-fg2 hover:bg-[var(--sel)] hover:text-fg"}`}>
                      {({ isActive }) => (
                        <>
                          {isActive && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-[var(--fg)] shadow-lg" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
                          <n.Icon size={19} className="relative shrink-0" />
                          {expanded && <span className="relative truncate text-sm font-medium">{n.label}</span>}
                        </>
                      )}
                    </NavLink>
                  ))}
                </LayoutGroup>
              </nav>
              <div className={`flex shrink-0 flex-col gap-1 pt-2 ${expanded ? "" : "items-center"}`}>
                <button aria-label="Log out" title="Log out" onClick={doLogout} className={`${row} h-11 text-fg2 hover:bg-[var(--sel)] hover:text-fg`}><LogOut size={18} className="shrink-0" />{expanded && <span className="truncate text-sm font-medium">Log out</span>}</button>
                <Link to="/profile" aria-label="Profile" className={`mt-1 flex items-center gap-3 ${expanded ? "px-1" : ""}`}>
                  {avatar}
                  {expanded && <span className="min-w-0 leading-tight"><span className="block truncate text-sm font-semibold">{user.name || user.email}</span><span className="block text-xs capitalize text-muted">{user.role}</span></span>}
                </Link>
              </div>
            </Glass>
          </motion.aside>

          {/* Route content crossfades; non-dashboard pages sit on a sheet so the CRUD screens stay legible */}
          <motion.main key={pathname} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: EASE }} className="min-w-0 flex-1 md:-m-2 md:h-[calc(100%+1rem)] md:overflow-y-auto md:overflow-x-hidden md:overscroll-contain md:p-2">
            {pathname === "/" ? <Outlet /> : <div className="sheet"><Outlet /></div>}
          </motion.main>
        </div>
      </div>

      {/* Bottom tab bar (<md) */}
      <nav aria-label="Main" className="no-print fixed inset-x-3 bottom-3 z-30 md:hidden">
        <Glass flat className="flex items-center justify-around px-1 py-1">
          {items.slice(0, 4).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `tap flex min-h-[48px] min-w-[56px] flex-col items-center justify-center gap-0.5 rounded-2xl px-2 text-[10px] font-medium ${isActive ? "bg-[var(--sel)] text-accent" : "text-fg2"}`}>
              <n.Icon size={19} />{n.label.split(" ")[0]}
            </NavLink>
          ))}
          <button onClick={() => setPalette(true)} className="tap flex min-h-[48px] min-w-[56px] flex-col items-center justify-center gap-0.5 rounded-2xl px-2 text-[10px] font-medium text-fg2"><Search size={19} />More</button>
        </Glass>
      </nav>

      <CommandPalette open={palette} onClose={() => setPalette(false)} items={cmds} />
    </div>
  );
}

export default function Layout() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <MotionConfig reducedMotion="user">
          <Shell />
        </MotionConfig>
      </ToastProvider>
    </ThemeProvider>
  );
}

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <ThemeProvider>
      <Backdrop />
      <div className="mx-auto max-w-md px-4 py-16">
        <h1 className="mb-1 text-3xl font-semibold tracking-tight">brightloop</h1>
        <h2 className="mb-6 text-fg2">{title}</h2>
        <div className="sheet">{children}</div>
      </div>
    </ThemeProvider>
  );
}
