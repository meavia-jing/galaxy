import { expect, test } from '@playwright/test'

import { loginViaUi, registerViaUi, uniqueUsername } from './helpers'

test.describe('认证链路', () => {
  test('[E2E-01][I02-T05] 注册后自动登录并跳转首页', async ({ page }) => {
    const username = uniqueUsername()
    const nickname = `E2E${username.slice(-4)}`

    await registerViaUi(page, username, nickname)

    // 头部出现昵称即证明内存态已写入；刷新后仍在线由 E2E-02 覆盖。
    await expect(page.locator('.site-header')).toContainText(`你好，${nickname}`)
    await expect(page.getByRole('link', { name: '个人中心' })).toBeVisible()
  })

  test('[E2E-02][I02-T05] 刷新页面后由 bootstrap 恢复会话', async ({ page }) => {
    await loginViaUi(page, 'demo', 'ShopDemo2026')
    const greeting = await page.locator('.site-header').innerText()
    expect(greeting).toContain('你好，')

    await page.reload()

    // access 只在内存中；刷新后必须靠 refresh Cookie 走 bootstrap 重新取回。
    await expect(page.locator('.site-header')).toContainText('你好，')
    await expect(page.getByRole('link', { name: '个人中心' })).toBeVisible()

    await page.getByRole('button', { name: '退出' }).click()
    await expect(page.getByRole('link', { name: '登录' })).toBeVisible()
  })

  test('[E2E-03][I02-T05] 退出后访问个人中心重定向到登录页', async ({ page }) => {
    await loginViaUi(page, 'demo', 'ShopDemo2026')
    await page.getByRole('button', { name: '退出' }).click()
    await expect(page.locator('.site-header')).not.toContainText('你好，')

    await page.goto('/account')

    await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)account/)
    await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()
  })
})
