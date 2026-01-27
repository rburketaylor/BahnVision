import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Transit brand colors (BVV-style)
        primary: {
          DEFAULT: '#0065AE', // U-Bahn blue
          dark: '#004677',
          light: '#4C9ACF',
        },
        ubahn: '#0065AE', // U-Bahn blue
        sbahn: '#00AB4E', // S-Bahn green
        tram: '#D60F26', // Tram red
        bus: '#00558C', // Bus dark blue

        // Status colors
        status: {
          critical: '#D60F26', // Tram red
          warning: '#F59E0B', // Amber
          healthy: '#00AB4E', // S-Bahn green
          neutral: '#6b7280', // Slate gray
        },

        // Surface layers
        surface: {
          1: '#0a0a0a', // Lowest layer (map container)
          2: '#121212', // Mid layer (floating panels)
          3: '#1E1E1E', // Highest layer (popups, dropdowns)
        },

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
      fontSize: {
        display: ['28px', { lineHeight: '1.2', fontWeight: '700' }],
        h1: ['24px', { lineHeight: '1.3', fontWeight: '700' }],
        h2: ['18px', { lineHeight: '1.4', fontWeight: '600' }],
        h3: ['16px', { lineHeight: '1.4', fontWeight: '600' }],
        body: ['14px', { lineHeight: '1.5', fontWeight: '400' }],
        small: ['12px', { lineHeight: '1.4', fontWeight: '400' }],
        tiny: ['11px', { lineHeight: '1.3', fontWeight: '500' }],
      },
      fontFamily: {
        sans: ['Inter', 'Roboto', 'system-ui', 'sans-serif'],
      },
      maxWidth: {
        '8xl': '88rem',
        '9xl': '96rem',
      },
      boxShadow: {
        'surface-top': '0 -1px 3px rgba(0, 0, 0, 0.12), 0 -1px 2px rgba(0, 0, 0, 0.24)',
        'card-hover': '0 8px 25px -5px rgba(0, 0, 0, 0.2), 0 4px 12px -2px rgba(0, 0, 0, 0.1)',
      },
      transitionDuration: {
        '150': '150ms',
        '250': '250ms',
        '300': '300ms',
      },
      transitionTimingFunction: {
        'bounce-in': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        'ease-out': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
      },
    },
  },
  plugins: [],
} satisfies Config
