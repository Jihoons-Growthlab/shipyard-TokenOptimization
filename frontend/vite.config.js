import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const proxy = { '/api': 'http://127.0.0.1:8000' }

export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', port: 5173, proxy },
  preview: { host: '127.0.0.1', port: 5173, proxy },
  test: { environment: 'jsdom', globals: true },
})
