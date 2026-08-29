/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: ["Fraunces", "ui-serif", "Georgia", "Cambria", "serif"],
        roboto: ["Roboto", "sans-serif"],
      },
      colors: {
        // Brand: the whole UI is green. "blue" is remapped to the green scale
        // so existing classes (bg-blue-*) shift to the brand colour without
        // touching every file, and "green" maps to the same scale so semantic
        // success/status states stay perfectly in sync with the brand.
        blue: {
          50: "#effaf4",
          100: "#d7f2e4",
          200: "#ace3c8",
          300: "#78cfa6",
          400: "#3fb37f",
          500: "#1f9a66",
          600: "#127a51",
          700: "#106342",
          800: "#115036",
          900: "#0f422d",
          950: "#062a1b",
        },
        green: {
          50: "#effaf4",
          100: "#d7f2e4",
          200: "#ace3c8",
          300: "#78cfa6",
          400: "#3fb37f",
          500: "#1f9a66",
          600: "#127a51",
          700: "#106342",
          800: "#115036",
          900: "#0f422d",
          950: "#062a1b",
        },
        paper: "#f7f5f0",
        ink: "#1c1b18",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.06)",
        card: "0 1px 3px rgba(16, 24, 40, 0.05), 0 12px 32px rgba(16, 24, 40, 0.08)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
