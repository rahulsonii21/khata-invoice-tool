/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        paper: '#FBFAF6',
        ink: {
          DEFAULT: '#1F3A34',
          light: '#3D5C54',
          faint: '#7C9089',
        },
        marigold: '#C98A1B',
        rust: '#A13D2B',
        sage: '#DCE5DE',
        line: '#D8D2C0',
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
