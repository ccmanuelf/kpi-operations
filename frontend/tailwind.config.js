/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1a237e',
        secondary: '#0d47a1',
        success: '#2e7d32',
        warning: '#f57c00',
        danger: '#c62828',
      }
    },
  },
  plugins: [],
}
