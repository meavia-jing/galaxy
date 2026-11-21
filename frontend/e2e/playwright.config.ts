import { defineConfig } from '@playwright/test'

/**
 * B7 Playwright E2E 骨架。
 *
 * - 复用系统 Chrome（channel: "chrome"），不下载 chromium，避免内网下载卡住。
 * - webServer 设 reuseExistingServer: true：本地已用 start-dev.ps1 起服务时直接复用；
 *   未启动时由 Playwright 拉起（Django 8000 + Vite 5173）。
 * - workers 固定 1：用例共用同一份演示数据，避免并发写库相互干扰。
 */
export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 40_000,
  expect: { timeout: 8_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'report' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    channel: 'chrome',
    locale: 'zh-CN',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: '../../.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000',
      cwd: '../../backend',
      url: 'http://127.0.0.1:8000/health/live/',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: '..',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
})
