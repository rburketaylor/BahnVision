import type { Config } from 'tailwindcss'
import tailwindcssAnimate from 'tailwindcss-animate'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        surface: {
          DEFAULT: 'hsl(var(--surface) / <alpha-value>)',
          elevated: 'hsl(var(--surface-elevated) / <alpha-value>)',
          muted: 'hsl(var(--surface-muted) / <alpha-value>)',
          1: 'hsl(var(--background) / <alpha-value>)',
          2: 'hsl(var(--surface) / <alpha-value>)',
          3: 'hsl(var(--surface-elevated) / <alpha-value>)',
        },
        interactive: {
          DEFAULT: 'hsl(var(--interactive) / <alpha-value>)',
          hover: 'hsl(var(--interactive-hover) / <alpha-value>)',
          active: 'hsl(var(--interactive-active) / <alpha-value>)',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary) / <alpha-value>)',
          foreground: 'hsl(var(--primary-foreground) / <alpha-value>)',
          dark: 'hsl(var(--interactive-active) / <alpha-value>)',
          light: 'hsl(var(--interactive-hover) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary) / <alpha-value>)',
          foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive) / <alpha-value>)',
          foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted) / <alpha-value>)',
          foreground: 'hsl(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent) / <alpha-value>)',
          foreground: 'hsl(var(--accent-foreground) / <alpha-value>)',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover) / <alpha-value>)',
          foreground: 'hsl(var(--popover-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT: 'hsl(var(--card) / <alpha-value>)',
          foreground: 'hsl(var(--card-foreground) / <alpha-value>)',
        },
        status: {
          healthy: 'hsl(var(--status-healthy) / <alpha-value>)',
          warning: 'hsl(var(--status-warning) / <alpha-value>)',
          critical: 'hsl(var(--status-critical) / <alpha-value>)',
          info: 'hsl(var(--status-info) / <alpha-value>)',
          neutral: 'hsl(var(--status-neutral) / <alpha-value>)',
        },
        ubahn: 'hsl(var(--transport-ubahn) / <alpha-value>)',
        sbahn: 'hsl(var(--transport-sbahn) / <alpha-value>)',
        tram: 'hsl(var(--transport-tram) / <alpha-value>)',
        bus: 'hsl(var(--transport-bus) / <alpha-value>)',
      },
      borderRadius: {
        sm: 'calc(var(--radius) - 2px)',
        md: 'var(--radius)',
        lg: 'calc(var(--radius) + 2px)',
        xl: 'calc(var(--radius) + 4px)',
      },
      fontSize: {
        display: [
          'clamp(2rem, 1.2rem + 2.8vw, 3.35rem)',
          { lineHeight: '1.02', fontWeight: '700' },
        ],
        h1: ['1.75rem', { lineHeight: '1.15', fontWeight: '700' }],
        h2: ['1.35rem', { lineHeight: '1.2', fontWeight: '600' }],
        h3: ['1.05rem', { lineHeight: '1.25', fontWeight: '600' }],
        body: ['0.925rem', { lineHeight: '1.45', fontWeight: '400' }],
        small: ['0.8rem', { lineHeight: '1.35', fontWeight: '500' }],
        tiny: ['0.72rem', { lineHeight: '1.25', fontWeight: '500' }],
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"Segoe UI"', 'sans-serif'],
        display: ['"Barlow Condensed"', '"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      maxWidth: {
        '8xl': '88rem',
        '9xl': '96rem',
      },
      boxShadow: {
        'surface-1': '0 1px 2px hsl(210 35% 10% / 0.1)',
        'surface-2': '0 8px 26px hsl(210 45% 10% / 0.14)',
        focus: '0 0 0 4px hsl(var(--ring) / 0.25)',
      },
      transitionDuration: {
        120: '120ms',
        180: '180ms',
        240: '240ms',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
        entrance: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [tailwindcssAnimate],
} satisfies Config
