import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // In production FastAPI serves the SPA and every API route from one
      // origin, so both `/api/open-org/*` (discovery, signals, editor) and the
      // public `/open-org/*` routes (profile.json, strategies, ideas, history)
      // resolve. In dev the SPA is served by Vite, so both path families must
      // be proxied to FastAPI. The SPA's own routes live under `/openorg`
      // (no hyphen), so `/open-org` does not collide with them.
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/open-org': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  ssr: {
    // Bundle these packages for SSR to handle CommonJS/ESM differences
    noExternal: ['react-helmet-async'],
  },
})
