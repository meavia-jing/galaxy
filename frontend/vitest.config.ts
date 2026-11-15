import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 前端单测：happy-dom 提供 document/cookie/history，无需真实浏览器。
// 用例文件与被测模块同目录（src/**/*.spec.ts），便于就近维护。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['src/**/*.spec.ts'],
    reporters: ['default'],
    clearMocks: true,
    restoreMocks: true,
  },
})
