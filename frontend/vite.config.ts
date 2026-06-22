import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const githubPagesRepository = 'kennechen554-code/AHR999-Optimized-Kenne-Index'
const base = process.env.GITHUB_REPOSITORY === githubPagesRepository ? '/AHR999-Optimized-Kenne-Index/' : '/'

export default defineConfig({
  base,
  plugins: [react(), tailwindcss()],
  build: {
    outDir: 'build',
    copyPublicDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
