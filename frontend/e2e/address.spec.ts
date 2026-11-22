import { expect, test, type Page } from '@playwright/test'

import { registerViaUi, uniqueUsername } from './helpers'

const PHONE = '13800138000'

/** 新增一条地址；默认收件人按入参区分，便于在一页多卡时精确定位。 */
async function createAddress(page: Page, recipient: string, detail: string): Promise<void> {
  await page.getByRole('button', { name: '新增地址' }).click()
  const form = page.locator('form.addr-form')
  await form.getByLabel('收件人').fill(recipient)
  await form.getByLabel('联系电话').fill(PHONE)
  await form.getByLabel('省', { exact: true }).fill('广东省')
  await form.getByLabel('市', { exact: true }).fill('深圳市')
  await form.getByLabel('区/县').fill('南山区')
  await form.getByLabel('详细地址').fill(detail)
  await page.getByRole('button', { name: '保存地址' }).click()
  await expect(page.getByRole('status')).toHaveText('地址已添加')
}

function cardOf(page: Page, recipient: string) {
  return page.locator('.addr-card').filter({ hasText: recipient })
}

test.describe('地址管理链路', () => {
  test('[E2E-05][I02-T04] 新增 → 改默认 → 编辑 → 删除 完整闭环', async ({ page }) => {
    const username = uniqueUsername('addr')
    await registerViaUi(page, username, `ADR${username.slice(-4)}`)

    // 新用户地址为空，避免依赖演示数据，也不会污染 demo 的地址。
    await page.goto('/account/addresses')
    await expect(page.getByText('还没有收货地址')).toBeVisible()

    // 第一条自动成为默认（后端规则），因此「改默认」需要第二条地址才有意义。
    await createAddress(page, 'E2E 收件人甲', '科技园路 1 号')
    const first = cardOf(page, 'E2E 收件人甲')
    await expect(first).toHaveCount(1)
    await expect(first.locator('.addr-badge')).toHaveText('默认')

    await createAddress(page, 'E2E 收件人乙', '科技园路 2 号')
    const second = cardOf(page, 'E2E 收件人乙')
    await expect(second).toHaveCount(1)

    // 改默认：徽标从甲移到乙，且乙的「设为默认」按钮消失、甲重新出现。
    await second.getByRole('button', { name: '设为默认' }).click()
    await expect(page.getByRole('status')).toHaveText('默认地址已切换')
    await expect(second.locator('.addr-badge')).toHaveText('默认')
    await expect(first.locator('.addr-badge')).toHaveCount(0)
    await expect(first.getByRole('button', { name: '设为默认' })).toBeVisible()

    // 编辑：表单必须预填原值，保存后列表回源显示新内容。
    await second.getByRole('button', { name: '编辑' }).click()
    const form = page.locator('form.addr-form')
    await expect(form.getByLabel('收件人')).toHaveValue('E2E 收件人乙')
    await expect(form.getByLabel('联系电话')).toHaveValue(PHONE)
    await form.getByLabel('详细地址').fill('科技园路 2 号（E2E 修改）')
    await page.getByRole('button', { name: '保存地址' }).click()

    await expect(page.getByRole('status')).toHaveText('地址已更新')
    await expect(second).toContainText('科技园路 2 号（E2E 修改）')

    // 删除：二次确认后列表回源，卡片消失；删掉默认项后甲应被自动提升为默认。
    page.once('dialog', (dialog) => dialog.accept())
    await second.getByRole('button', { name: '删除' }).click()
    await expect(page.getByRole('status')).toHaveText('地址已删除')
    await expect(cardOf(page, 'E2E 收件人乙')).toHaveCount(0)
    await expect(first.locator('.addr-badge')).toHaveText('默认')

    // 清理：删除最后一条，该用户不留数据。
    page.once('dialog', (dialog) => dialog.accept())
    await first.getByRole('button', { name: '删除' }).click()
    await expect(page.getByText('还没有收货地址')).toBeVisible()
  })

  test('[E2E-06][I02-T05] 390×844 视口下各页面无横向滚动', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const username = uniqueUsername('mob')
    await registerViaUi(page, username, `MOB${username.slice(-4)}`)

    // 含 /cart：购物车行在窄屏改为单列网格，是最容易撑破视口的页面之一。
    for (const path of ['/', '/products', '/account/addresses', '/cart']) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      )
      expect(overflow, `${path} 出现横向滚动 ${overflow}px`).toBeLessThanOrEqual(1)
    }
  })
})
