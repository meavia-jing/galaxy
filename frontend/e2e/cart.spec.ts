import { expect, test } from '@playwright/test'

import { loginViaUi, registerViaUi, uniqueUsername } from './helpers'

test.describe('购物车链路', () => {
  test('[E2E-07][I04-T01] 详情页加购 → 购物车改数量 → 移除', async ({ page }) => {
    const username = uniqueUsername('cart')
    await registerViaUi(page, username, `CART${username.slice(-4)}`)

    // 从列表进详情，选第一个可买规格后加购。
    await page.goto('/products')
    const firstCard = page.locator('.grid .card').first()
    await expect(firstCard).toBeVisible()
    const title = (await firstCard.locator('.card__title').innerText()).trim()
    await firstCard.click()

    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
    await page.getByLabel('购买数量').fill('2')
    await page.getByRole('button', { name: '加入购物车' }).click()
    await expect(page.getByRole('status')).toContainText('已加入购物车（2 件）')

    // 购物车只有一行，数量为 2，小计由服务端给出。
    await page.goto('/cart')
    const row = page.locator('.cart-row')
    await expect(row).toHaveCount(1)
    await expect(row.locator('.cart-row__title')).toHaveText(title)
    await expect(row.locator('.cart-row__input')).toHaveValue('2')
    await expect(row.locator('.cart-row__amount')).toHaveText(/¥\d+\.\d{2}/)

    // 改数量：同 SKU 仍是一行，金额随之变化。
    const amountBefore = await row.locator('.cart-row__amount').innerText()
    await row.locator('.cart-row__input').fill('3')
    await row.locator('.cart-row__input').blur()
    await expect(page.getByRole('status')).toHaveText('数量已更新')
    await expect(row.locator('.cart-row__amount')).not.toHaveText(amountBefore)

    // 移除后回到空态。
    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: '移除' }).click()
    await expect(page.getByRole('status')).toHaveText('已从购物车移除')
    await expect(page.getByText('购物车还是空的')).toBeVisible()
  })

  test('[E2E-08][I04-T01] 未登录访问购物车重定向登录', async ({ page }) => {
    await page.goto('/cart')

    await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)cart/)
    await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()

    await loginViaUi(page, 'demo', 'ShopDemo2026')
    await page.goto('/cart')
    await expect(page.getByRole('heading', { name: '购物车' })).toBeVisible()
  })
})
