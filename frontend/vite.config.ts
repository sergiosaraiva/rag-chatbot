import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_CHATBOT_NAME': JSON.stringify(process.env.VITE_CHATBOT_NAME),
    'import.meta.env.VITE_CHATBOT_USER': JSON.stringify(process.env.VITE_CHATBOT_USER),
    'import.meta.env.VITE_MAX_MESSAGES': JSON.stringify(process.env.VITE_MAX_MESSAGES)
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://backend:8000',
        changeOrigin: true,
      }
    }
  },
  preview: {
    port: 3000,
    host: true,
    allowedHosts: ['frontend-production-3d98.up.railway.app']
  },
  build: {
    outDir: 'dist'
  }
})