import type { Config } from 'tailwindcss'

export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // MVG brand colors
        primary: {
          DEFAULT: '#0065AE', // MVG blue
          dark: '#004677',
          light: '#4C9ACF',
        },
        ubahn: '#0065AE',  // U-Bahn blue
        sbahn: '#00AB4E',  // S-Bahn green
        tram: '#D60F26',   // Tram red
        bus: '#00558C',    // Bus dark blue
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
