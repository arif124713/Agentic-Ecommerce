import { configDefaults, defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    // e2e/*.spec.ts are Playwright tests (real `test`/`expect` from @playwright/test, run via
    // `npx playwright test`) — same filename pattern as vitest's own default, so they need an
    // explicit exclude or vitest tries to run them too and fails on the mismatched test API.
    exclude: [...configDefaults.exclude, '**/e2e/**'],
  },
})
