/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "sans-serif",
        ],
        display: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      colors: {
        ink: {
          950: "#070708",
          900: "#0b0b0d",
          850: "#101012",
          800: "#15151a",
          750: "#1a1a20",
          700: "#22222a",
          600: "#2c2c36",
          500: "#3a3a47",
          400: "#5b5b6b",
          300: "#8b8b9a",
          200: "#bcbcc8",
          100: "#e7e7ec",
        },
        accent: {
          DEFAULT: "#f5a623",
          soft: "#f5a62333",
          deep: "#c97c10",
        },
        ok: "#3ddc97",
        warn: "#f5c542",
        err: "#ef5350",
      },
      borderRadius: {
        card: "1.5rem",
        chip: "999px",
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 30px 60px -30px rgba(0,0,0,0.6)",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        pulseSoft: "pulseSoft 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
