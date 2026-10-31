/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", '"SF Pro Display"', "Inter", "system-ui", "sans-serif"],
        mono: ['"SF Mono"', "ui-monospace", "Menlo", "monospace"],
      },
      // Theme colours are CSS variables (src/index.css) so dark/light swap without touching components.
      colors: { fg: "var(--fg)", fg2: "var(--fg2)", muted: "var(--muted)", accent: "var(--accent)" },
    },
  },
  plugins: [],
};
