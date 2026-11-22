import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError } from '@/api/http'
import type { CartItem, CartSummary } from '@/api/types'

const mocks = vi.hoisted(() => ({
  fetchCart: vi.fn(),
  updateCartItem: vi.fn(),
  removeCartItem: vi.fn(),
}))

vi.mock('@/api/cart', () => mocks)

import CartView from '@/views/CartView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

function item(overrides: Partial<CartItem> = {}): CartItem {
  return {
    id: '1',
    sku_id: 'sku-1',
    product_id: 'p-1',
    product_title: '云集蓝牙耳机',
    sku_code: 'EAR-BLACK',
    attributes: { 颜色: '黑色' },
    unit_price: '99.00',
    quantity: 2,
    line_amount: '198.00',
    selected: true,
    stock_available: 5,
    available: true,
    unavailable_reason: '',
    ...overrides,
  }
}

function summary(overrides: Partial<CartSummary> = {}): CartSummary {
  const items = overrides.items ?? [item()]
  return {
    items,
    selected_count: items.filter((row) => row.selected && row.available).length,
    subtotal: '198.00',
    has_unavailable: items.some((row) => !row.available),
    ...overrides,
  }
}

async function mountView() {
  const wrapper = mount(CartView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  mocks.fetchCart.mockReset().mockResolvedValue(summary())
  mocks.updateCartItem.mockReset().mockResolvedValue(item())
  mocks.removeCartItem.mockReset().mockResolvedValue(undefined)
})

describe('CartView', () => {
  it('[UNIT-FE-30][I04-T01] 渲染列表，小计取服务端金额而非前端相加', async () => {
    // 故意让服务端小计与「行金额之和」不同：前端必须显示服务端的值。
    mocks.fetchCart.mockResolvedValue(
      summary({ items: [item({ line_amount: '198.00' }), item({ id: '2', line_amount: '50.00' })], subtotal: '248.00', selected_count: 2 }),
    )
    const wrapper = await mountView()

    expect(wrapper.findAll('.cart-row')).toHaveLength(2)
    expect(wrapper.get('.cart-foot__price').text()).toBe('¥248.00')
    expect(wrapper.text()).toContain('已选 2 件')
    expect(wrapper.text()).toContain('黑色 · 单价 ¥99.00')
  })

  it('[UNIT-FE-31][I04-T01] 下架项标红、勾选禁用、显示原因且不计入小计', async () => {
    mocks.fetchCart.mockResolvedValue(
      summary({
        items: [item({ id: '9', available: false, unavailable_reason: '商品已下架', selected: false })],
        subtotal: '0.00',
        selected_count: 0,
        has_unavailable: true,
      }),
    )
    const wrapper = await mountView()

    expect(wrapper.get('.cart-row').classes()).toContain('cart-row--off')
    expect(wrapper.get('.cart-row__warn').text()).toBe('商品已下架')
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).disabled).toBe(true)
    expect(wrapper.get('.cart-foot__price').text()).toBe('¥0.00')
    expect(wrapper.text()).toContain('存在已下架或库存不足的商品')
  })

  it('[UNIT-FE-32][I04-T01] 空购物车显示空态与去逛逛入口', async () => {
    mocks.fetchCart.mockResolvedValue(summary({ items: [], subtotal: '0.00', selected_count: 0 }))
    const wrapper = await mountView()

    expect(wrapper.find('.empty').text()).toContain('购物车还是空的')
    expect(wrapper.findAll('.cart-row')).toHaveLength(0)
  })

  it('[UNIT-FE-33][I04-T01] 加载失败展示错误并可重试', async () => {
    mocks.fetchCart.mockRejectedValueOnce(new Error('后端不可用'))
    const wrapper = await mountView()

    expect(wrapper.find('.empty').text()).toContain('后端不可用')

    await wrapper.findAll('button').find((btn) => btn.text() === '重新加载')?.trigger('click')
    await flushPromises()

    expect(mocks.fetchCart).toHaveBeenCalledTimes(2)
  })

  it('[UNIT-FE-34][I04-T01] 勾选切换提交取反后的 selected 并刷新', async () => {
    const wrapper = await mountView()

    await wrapper.get('input[type="checkbox"]').trigger('change')
    await flushPromises()

    expect(mocks.updateCartItem).toHaveBeenCalledWith('1', { selected: false })
    expect(mocks.fetchCart).toHaveBeenCalledTimes(2)
  })

  it('[UNIT-FE-35][I04-T01] 数量越界时前端拦截，不发请求', async () => {
    const wrapper = await mountView()

    const input = wrapper.get('.cart-row__input')
    await input.setValue('0')
    await input.trigger('change')
    await flushPromises()

    expect(mocks.updateCartItem).not.toHaveBeenCalled()
    expect(wrapper.find('[role="alert"]').text()).toContain('数量需在 1 至 99 之间')
  })

  it('[UNIT-FE-36][I04-T01] 合法数量提交后提示已更新', async () => {
    const wrapper = await mountView()

    const input = wrapper.get('.cart-row__input')
    await input.setValue('4')
    await input.trigger('change')
    await flushPromises()

    expect(mocks.updateCartItem).toHaveBeenCalledWith('1', { quantity: 4 })
    expect(wrapper.get('[role="status"]').text()).toBe('数量已更新')
  })

  it('[UNIT-FE-37][I04-T01] 移除需二次确认，取消则不请求', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '移除')?.trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(mocks.removeCartItem).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('[UNIT-FE-37][I04-T01] 确认后删除并提示', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '移除')?.trigger('click')
    await flushPromises()

    expect(mocks.removeCartItem).toHaveBeenCalledWith('1')
    expect(wrapper.get('[role="status"]').text()).toBe('已从购物车移除')
    confirmSpy.mockRestore()
  })

  it('[UNIT-FE-38][I04-T01] 服务端拒绝时把字段文案作为提示', async () => {
    mocks.updateCartItem.mockRejectedValue(
      new ApiRequestError({
        code: 'INSUFFICIENT_STOCK',
        message: '库存不足，当前仅剩 1 件',
      }),
    )
    const wrapper = await mountView()

    await wrapper.get('input[type="checkbox"]').trigger('change')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('库存不足，当前仅剩 1 件')
  })
})
