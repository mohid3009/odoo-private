import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ReactNode, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import LatticeLoader from "./LatticeLoader";

const FLAG = "bl_splash"; // once per browser tab session: reloads and in-app navigation skip it
const MIN_MS = 2200; // long enough for the lattice to run a couple of laps
const FINISH_MS = 650; // the check mark holds this long before the screen fades away

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
    const t = setTimeout(() => { // let the dots resolve into the check before leaving
      try { sessionStorage.setItem(FLAG, "1"); } catch { /* ignore */ }
      document.documentElement.classList.remove("boot");
      setShow(false);
    }, FINISH_MS);
    return () => clearTimeout(t);
  }, [ready]);

  return (
    <>
      {children}
      <AnimatePresence>{show && <Splash key="splash" done={ready} />}</AnimatePresence>
    </>
  );
}

// Pure black, no text: a 4x4 lattice of glowing chrome-white dots running an orbit, then a check mark when the app is ready.
function Splash({ done }: { done: boolean }) {
  const calm = useReducedMotion();
  return (
    <motion.div
      role="status" aria-live="polite" aria-label="Loading"
      className="fixed inset-0 z-[9999] grid place-items-center overflow-hidden bg-black"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, scale: calm ? 1 : 1.05 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      <LatticeLoader
        status={done ? "done" : "working"}
        label="" doneLabel="" errorLabel="" showTimer={false} fontSize={0}
        grid={4} pattern="orbit" shape="round" cellSize={18} gap={8} step={110} idleOpacity={0.1}
        color="#e9eef4" doneColor="#ffffff" glow glowColor="rgba(190, 210, 240, 0.65)"
      />
    </motion.div>
  );
}
