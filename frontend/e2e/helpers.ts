import { expect, type Page } from '@playwright/test'

export const E2E_PASSWORD = 'ShopE2e20260'

/** 每个用例自建用户，命名带随机后缀，避免相互污染演示数据。 */
export function uniqueUsername(prefix = 'e2e'): string {
  return `${prefix}${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
}

/** 通过真实注册页建号并等待跳转首页（同时验证注册→自动登录链路）。 */
export async function registerViaUi(page: Page, username: string, nickname: string): Promise<void> {
  await page.goto('/register')
  const form = page.locator('form.auth-card')
  await form.getByLabel(/^用户名/).fill(username)
  await form.getByLabel(/^昵称/).fill(nickname)
  await form.getByLabel(/^密码/).fill(E2E_PASSWORD)
  await form.getByLabel(/^确认密码/).fill(E2E_PASSWORD)
  await form.getByRole('button', { name: '注册并登录' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.locator('.site-header')).toContainText(`你好，${nickname}`)
}

/** 通过登录页登录，并断言头部出现昵称。 */
export async function loginViaUi(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/login')
  const form = page.locator('form.auth-card')
  await form.getByLabel(/^用户名/).fill(username)
  await form.getByLabel(/^密码/).fill(password)
  await form.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.locator('.site-header')).toContainText('你好，')
}
