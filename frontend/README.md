# Brightloop frontend: glass dashboard

React 18 + Tailwind + Recharts + Framer Motion + Lucide.

## Theme
All colours, blur, radii and shadows are CSS variables at the top of `src/index.css`
(`:root` = light, the default; `:root[data-theme="dark"]` = dark). Palette follows Apple's system colours: blue `#0A84FF` accent, green `#30D158`, orange `#FF9F0A`, red `#FF453A`, neutral greys, SF font stack with Inter fallback. Tailwind maps `fg`, `fg2`, `muted`, `accent` to them
(`tailwind.config.js`). Change `--glass`, `--blur`, `--radius-w` to restyle every widget at once.
The glass recipe is the single `.glass` class; the ambient blobs are in `Layout.tsx` (`Blobs`, a faint blue wash).

## Add a widget
1. Write a component in `src/features/insight/widgets.tsx` that returns `<WidgetCard title info className=…>`.
   `WidgetCard` provides the glass surface, header pattern, and staggered entrance.
2. Drop it in the grid in `Home.tsx` and give it column spans (`md:col-span-*`, `xl:col-span-*`, 12-col grid).
3. Charts live in `src/components/charts/charts.tsx`; keep them gradient + rounded + no heavy grid.

## Data
Live: counts, recent invoices, `/api/healthz`. Sample: everything fed by `src/data/mock.ts`.
To go live, replace the `factory` passed to `useMock(key, factory)` with an `api.get(...)` call. The hook's
`keepPreviousData` makes charts morph between datasets instead of flashing skeletons.
The global date range (7/30/90d) drives the sample widgets only; the live counts are all-time.

## Accessibility and motion
Visible teal focus ring, ⌘K / Ctrl+K palette (↑ ↓ Enter Esc), 44px tap targets on touch devices,
`prefers-reduced-motion` disables transforms (via `MotionConfig`) and CSS animations.
`--muted` is lifted slightly from the brief's #5F7186 so small text stays AA on glass.
