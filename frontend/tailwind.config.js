/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: '#FBFAF6',
        ink: {
          DEFAULT: '#0B4A28',
          light: '#2E7D52',
          faint: '#6B8577',
        },
        leaf: '#00A344',
        marigold: '#C98A1B',
        rust: '#A13D2B',
        sage: '#DCEEE0',
        line: '#D3DBD1',
      },
      fontFamily: {
        display: ['"IBM Plex Serif"', 'serif'],
        sans: ['"IBM Plex Sans"', '"Noto Sans Devanagari"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
