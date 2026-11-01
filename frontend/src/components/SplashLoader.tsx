import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ReactNode, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";

const FLAG = "bl_splash"; // once per browser tab session: reloads and in-app navigation skip it
const MIN_MS = 2400; // long enough for the wireframe to draw itself in and breathe once

const seen = () => {
  try { return sessionStorage.getItem(FLAG) === "1"; } catch { return true; } // storage blocked: don't trap people behind a splash
};

// Wrap the app: children render (and fetch) underneath while the splash covers them, then it eases away.
export function SplashGate({ children }: { children: ReactNode }) {
  const { loading } = useAuth();
  const [show, setShow] = useState(() => !seen());
  const [minDone, setMinDone] = useState(false);
  const ready = minDone && !loading;

  useEffect(() => {
    if (!show) return void document.documentElement.classList.remove("boot");
    const t = setTimeout(() => setMinDone(true), MIN_MS);
    return () => clearTimeout(t);
  }, [show]);

  useEffect(() => {
    if (!ready) return;
    try { sessionStorage.setItem(FLAG, "1"); } catch { /* ignore */ }
    document.documentElement.classList.remove("boot");
    setShow(false);
  }, [ready]);

  return (
    <>
      {children}
      <AnimatePresence>{show && <Splash key="splash" />}</AnimatePresence>
    </>
  );
}

// An isometric cube as a wireframe: the hexagon outline plus six spokes from the centre to every corner (the hidden edges show through).
const K = 0.866; // cos(30deg)
function cubePath(s: number) {
  const v = [[0, -s], [K * s, -s / 2], [K * s, s / 2], [0, s], [-K * s, s / 2], [-K * s, -s / 2]];
  const hex = `M${v.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join("L")}Z`;
  const spokes = v.map(([x, y]) => `M0 0L${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  return hex + spokes;
}

// Three nested cubes: size, draw-in delay, bob phase.
const CUBES = [
  { s: 96, delay: 0.1, bob: 0, w: 1.6 },
  { s: 60, delay: 0.55, bob: 0.35, w: 1.4 },
  { s: 28, delay: 1.0, bob: 0.7, w: 1.2 },
] as const;

function Splash() {
  const calm = useReducedMotion();
  return (
    <motion.div
      role="status" aria-live="polite" aria-label="Loading"
      className="fixed inset-0 z-[9999] grid place-items-center overflow-hidden bg-black"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, scale: calm ? 1 : 1.06 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <svg viewBox="-220 -220 440 440" className="h-[min(78vmin,460px)] w-[min(78vmin,460px)]" fill="none" aria-hidden>
        <defs>
          {/* brushed-chrome: bright / dark bands, the whole ramp slides across the shape like light moving over metal */}
          <linearGradient id="bl-chrome" gradientUnits="userSpaceOnUse" x1="-220" y1="-220" x2="220" y2="220">
            <stop offset="0" stopColor="#ffffff" />
            <stop offset="0.18" stopColor="#8d98a5" />
            <stop offset="0.34" stopColor="#f4f7fb" />
            <stop offset="0.5" stopColor="#4a525b" />
            <stop offset="0.66" stopColor="#e9eef4" />
            <stop offset="0.84" stopColor="#7d8793" />
            <stop offset="1" stopColor="#ffffff" />
            {!calm && <animateTransform attributeName="gradientTransform" type="translate" values="-440 -440; 440 440" dur="3.2s" repeatCount="indefinite" />}
          </linearGradient>
          <filter id="bl-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.2" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* isometric orbit: a squashed circle with a dash that crawls, and a bright bead riding it */}
        <g transform="translate(0 22)">
          <motion.ellipse
            cx="0" cy="0" rx="190" ry="95" stroke="url(#bl-chrome)" strokeWidth="1" strokeDasharray="2 9" strokeLinecap="round"
            initial={{ opacity: 0 }} animate={{ opacity: 0.7 }} transition={{ delay: 0.3, duration: 1.2 }}
          />
          {!calm && (
            <circle r="3.2" fill="#fff" filter="url(#bl-glow)">
              <animateMotion dur="3.6s" repeatCount="indefinite" path="M190 0 A190 95 0 1 1 -190 0 A190 95 0 1 1 190 0" />
            </circle>
          )}
        </g>

        {/* the cubes: each draws itself in, then they float and breathe out of phase */}
        <g filter="url(#bl-glow)">
          {CUBES.map(({ s, delay, bob, w }) => (
            <motion.g
              key={s}
              animate={calm ? undefined : { y: [0, -9, 0], scale: [1, 1.035, 1] }}
              transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut", delay: bob }}
              style={{ transformOrigin: "0px 0px" }}
            >
              <motion.path
                d={cubePath(s)} stroke="url(#bl-chrome)" strokeWidth={w} strokeLinejoin="round" strokeLinecap="round"
                initial={{ pathLength: calm ? 1 : 0, opacity: calm ? 1 : 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ delay, duration: 1.3, ease: [0.22, 1, 0.36, 1] }}
              />
            </motion.g>
          ))}
        </g>
      </svg>
    </motion.div>
  );
}
