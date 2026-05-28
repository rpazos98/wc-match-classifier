import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'ghpages' ? '/wc-match-classifier/' : '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: mode === 'ghpages' ? 'dist' : '../static/dist',
    emptyOutDir: true,
  },
}))
