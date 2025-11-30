import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Enable source maps for debugging in production
    sourcemap: true,
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
          // Map related libraries (large, rarely used)
          'map-vendor': ['leaflet', 'react-leaflet'],
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
    // Optimize chunks
    chunkSizeWarningLimit: 1000,
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
      'leaflet',
      'react-leaflet',
    ],
  },
  server: {
    // Enable HMR for better development experience
    hmr: {
      overlay: false,
    },
  },
})
