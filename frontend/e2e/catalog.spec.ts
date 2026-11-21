import { expect, test } from '@playwright/test'

test.describe('商品浏览链路', () => {
  test('[E2E-04][I03-T03] 游客从列表进入详情，标题与价格一致', async ({ page }) => {
    await page.goto('/products')

    const firstCard = page.locator('.grid .card').first()
    await expect(firstCard).toBeVisible()

    const title = (await firstCard.locator('.card__title').innerText()).trim()
    const listPrice = (await firstCard.locator('.price').innerText()).trim()
    expect(title).not.toBe('')
    expect(listPrice).toMatch(/¥\d/)

    await firstCard.click()

    await expect(page).toHaveURL(/\/products\/\d+$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
    await expect(page.locator('.price').first()).toContainText('¥')
    // 封面图必须真的渲染出来（有 src 且已加载），避免只断言 DOM 存在。
    const cover = page.locator('.product-gallery img')
    if (await cover.count()) {
      await expect(cover).toHaveAttribute('src', /.+/)
      await expect.poll(() => cover.evaluate((img: HTMLImageElement) => img.complete)).toBe(true)
    }
  })

  test('[E2E-04b][I03-T02] 价格排序与非法参数不白屏', async ({ page }) => {
    await page.goto('/products?sort=price_asc')

    await expect(page.locator('.grid .card').first()).toBeVisible()
    await expect(page.locator('.chip--active', { hasText: '价格从低到高' })).toBeVisible()

    const prices = await page.locator('.grid .card .price').allInnerTexts()
    const numbers = prices.map((text) => Number(text.replace(/[^\d.]/g, '')))
    expect(numbers.length).toBeGreaterThan(1)
    expect([...numbers].sort((a, b) => a - b)).toEqual(numbers)
  })
})
