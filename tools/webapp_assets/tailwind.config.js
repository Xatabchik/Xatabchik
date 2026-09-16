/** @type {import('tailwindcss').Config} */
const path = require("path");

const webapp = path.resolve(__dirname, "../../src/shop_bot/webapp");

module.exports = {
  darkMode: "class",
  content: [
    path.join(webapp, "app.html"),
    path.join(webapp, "login.html"),
    path.join(webapp, "module/load.html"),
    path.join(webapp, "web_router/**/*.py"),
  ],
  theme: {
    extend: {
      colors: {
        primary: "#10b981",
        "background-light": "#f3f4f6",
        "background-dark": "#0a0a0a",
        "surface-light": "#ffffff",
        "surface-dark": "#171717",
        "surface-highlight-dark": "#262626",
        surface: {
          dark: "#121212",
          card: "#1e1e1e",
          highlight: "#2a2a2a",
        },
      },
      fontFamily: {
        display: ["Inter", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.75rem",
        xl: "1rem",
        "2xl": "1.5rem",
      },
      animation: {
        "spin-slow": "spin 3s linear infinite",
        "pulse-fast": "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
  ],
};
