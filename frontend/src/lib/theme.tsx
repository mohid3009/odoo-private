import { createContext, ReactNode, useContext, useEffect, useState } from "react";

export type Theme = "dark" | "light";
export type Range = 7 | 30 | 90; // global date-range filter (days)

interface Ctx {
  theme: Theme;
  toggle: () => void;
  range: Range;
  setRange: (r: Range) => void;
  endDate: string; // YYYY-MM-DD the range ends on; "" means today
  setEndDate: (d: string) => void;
}
const C = createContext<Ctx | null>(null);

function stored(): Theme {
  try {
    return localStorage.getItem("bl-theme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

// Theme + global filters live together: both are "app chrome" state that every widget reads.
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(stored);
  const [range, setRange] = useState<Range>(30);
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    const el = document.documentElement;
    el.classList.add("theme-fade"); // cross-fades colours for 0.5 s (see index.css)
    el.dataset.theme = theme;
    try { localStorage.setItem("bl-theme", theme); } catch { /* private mode */ }
    const t = setTimeout(() => el.classList.remove("theme-fade"), 500);
    return () => clearTimeout(t);
  }, [theme]);

  return (
    <C.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")), range, setRange, endDate, setEndDate }}>
      {children}
    </C.Provider>
  );
}

function useCtx() {
  const c = useContext(C);
  if (!c) throw new Error("ThemeProvider missing");
  return c;
}
export const useTheme = () => {
  const { theme, toggle } = useCtx();
  return { theme, toggle };
};
export const useRange = () => {
  const { range, setRange, endDate, setEndDate } = useCtx();
  return { range, setRange, endDate, setEndDate };
};
