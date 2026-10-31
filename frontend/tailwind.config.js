/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Inter Tight"',
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
      },
      letterSpacing: {
        tightest: '-0.04em',
        widestcustom: '0.25em',
      },
      lineHeight: {
        hero: '0.95',
      },
      colors: {
        chromegrey: '#9A9AA3',
        subsilver: '#C8C8D0',
        microgrey: '#8A8A94',
        darkbase: '#0B0B0D',
      },
    },
  },
  plugins: [],
};
