import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    // Only enable source maps in development, not production (security hardening)
    sourcemap: process.env.NODE_ENV !== 'production',
    // Generate bundle analysis
    rollupOptions: {
      output: {
        // Manual chunk splitting for better caching
        manualChunks: {
          // React and its ecosystem
          'react-vendor': ['react', 'react-dom', 'react-router'],
          // State management and data fetching
          'state-management': ['@tanstack/react-query', 'zustand'],
          // UI components (if we had any heavy ones)
          'ui-components': ['@headlessui/react'],
          // Map related libraries (large)
          'map-vendor': ['maplibre-gl'],
          // Error tracking
          monitoring: ['@sentry/react'],
        },
        // Optimize chunk naming for better caching
        chunkFileNames: chunkInfo => {
          const facadeModuleId = chunkInfo.facadeModuleId
            ? chunkInfo.facadeModuleId.split('/').pop()
            : 'chunk'
          return `assets/${facadeModuleId}-[hash].js`
        },
      },
    },
    // MapLibre GL is ~1011KB minified - just over the default 1000KB limit
    chunkSizeWarningLimit: 1100,
    // CSS code splitting
    cssCodeSplit: true,
  },
  // Optimize dependencies during development
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router',
      '@tanstack/react-query',
      'zustand',
      '@headlessui/react',
      'maplibre-gl',
    ],
  },
  server: {
    // Enable HMR for better development experience
    hmr: {
      overlay: false,
    },
  },
})
