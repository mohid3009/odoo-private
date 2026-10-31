import type { CSSProperties } from "react";

// The component is plain JS (from React Bits); this file only gives TypeScript its props.
export interface GrainientProps {
  colors?: string[];
  type?: "linear" | "radial";
  angle?: number;
  bands?: number;
  softness?: number;
  flow?: number;
  scale?: number;
  speed?: number;
  silk?: number;
  grainAmount?: number;
  grainSize?: number;
  grainAnimated?: boolean;
  contrast?: number;
  saturation?: number;
  variation?: number;
  interactive?: boolean;
  stir?: number;
  clickSwirl?: boolean;
  intro?: boolean;
  lightMode?: boolean;
  dpr?: number;
  className?: string;
  style?: CSSProperties;
}
declare const Grainient: (props: GrainientProps) => JSX.Element;
export default Grainient;
