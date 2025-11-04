import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
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

        // Dark theme palette
        background: '#121212',
        foreground: '#E0E0E0',
        card: '#1E1E1E',
        'card-foreground': '#E0E0E0',
        border: '#2C2C2C',
        input: '#2C2C2C',
      },
      fontFamily: {
        sans: ['Inter', 'Roboto', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
