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

        // Light theme palette (for consistency)
        light: {
          background: '#ffffff',
          foreground: '#111827',
          card: '#ffffff',
          'card-foreground': '#111827',
          border: '#e5e7eb',
          input: '#ffffff',
        },

        // Additional utility colors
        muted: {
          DEFAULT: '#6b7280',
          foreground: '#374151',
        },
        secondary: {
          DEFAULT: '#6b7280',
          foreground: '#ffffff',
        },
        accent: {
          DEFAULT: '#0065AE',
          foreground: '#ffffff',
        },

        },
      fontFamily: {
        sans: ['Inter', 'Roboto', 'system-ui', 'sans-serif'],
      },
      maxWidth: {
        '8xl': '88rem',
        '9xl': '96rem',
      }
    },
  },
  plugins: [],
} satisfies Config
