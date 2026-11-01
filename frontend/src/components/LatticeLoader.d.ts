// Types for LatticeLoader.jsx (React Bits component, JS + CSS variant), so the TypeScript app can import it.
import type { ComponentType, CSSProperties } from "react";

export interface LatticeLoaderProps {
  label?: string;
  doneLabel?: string;
  errorLabel?: string;
  status?: "working" | "done" | "error";
  pattern?: string | { cells: (number | null)[]; loop?: number; scale?: number; lit?: number };
  grid?: 3 | 4;
  shape?: "square" | "round";
  color?: string;
  doneColor?: string;
  errorColor?: string;
  cellSize?: number;
  gap?: number;
  fontSize?: number;
  step?: number;
  idleOpacity?: number;
  glow?: boolean;
  glowColor?: string;
  showTimer?: boolean;
  elapsed?: number;
  className?: string;
  style?: CSSProperties;
}

declare const LatticeLoader: ComponentType<LatticeLoaderProps>;
export default LatticeLoader;
