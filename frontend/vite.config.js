/** Configure Vite's React server and same-origin backend API proxy. */

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', '')
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: environment.API_PROXY_TARGET || 'http://localhost:5000',
          changeOrigin: true,
        },
      },
    },
  }
})
