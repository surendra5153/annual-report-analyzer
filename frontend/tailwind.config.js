/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#e8470a',
          50: '#1f0a03',
          400: '#f97316',
          500: '#e8470a',
          600: '#d13d07',
          700: '#c43606',
        },
        surface: {
          DEFAULT: '#161616',
          50: '#0c0c0c',
          100: '#111111',
          200: '#161616',
          300: '#1c1c1c',
          400: '#222222',
          border: '#252525',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease both',
        'slide-up': 'fadeUp 0.2s ease both',
      },
    },
  },
  plugins: [],
}
