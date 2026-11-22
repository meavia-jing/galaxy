import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}))

vi.mock('@/api/http', () => mocks)

import { addToCart, fetchCart, fetchCartItems, removeCartItem, updateCartItem } from '@/api/cart'

beforeEach(() => {
  mocks.apiGet.mockReset().mockResolvedValue(undefined)
  mocks.apiPost.mockReset().mockResolvedValue(undefined)
  mocks.apiPatch.mockReset().mockResolvedValue(undefined)
  mocks.apiDelete.mockReset().mockResolvedValue(undefined)
})

describe('cart api', () => {
  it('[UNIT-FE-25][I04-T01] 汇总接口走 /cart/，列表走 /cart-items/', () => {
    fetchCart()
    fetchCartItems()

    expect(mocks.apiGet.mock.calls[0][0]).toBe('/cart/')
    expect(mocks.apiGet.mock.calls[1][0]).toBe('/cart-items/')
  })

  it('[UNIT-FE-26][I04-T01] 加购提交 sku_id 与数量，默认勾选', () => {
    addToCart('sku-9', 3)

    expect(mocks.apiPost).toHaveBeenCalledWith('/cart-items/', {
      sku_id: 'sku-9',
      quantity: 3,
      selected: true,
    })
  })

  it('[UNIT-FE-27][I04-T01] 修改数量只提交 quantity，不带全量字段', () => {
    updateCartItem('item-2', { quantity: 5 })

    expect(mocks.apiPatch).toHaveBeenCalledWith('/cart-items/item-2/', { quantity: 5 })
    expect(Object.keys(mocks.apiPatch.mock.calls[0][1])).toEqual(['quantity'])
  })

  it('[UNIT-FE-28][I04-T01] 勾选切换只提交 selected', () => {
    updateCartItem('item-3', { selected: false })

    expect(mocks.apiPatch).toHaveBeenCalledWith('/cart-items/item-3/', { selected: false })
  })

  it('[UNIT-FE-29][I04-T01] 移除走 DELETE，路径带尾部斜杠', () => {
    removeCartItem('item-4')

    expect(mocks.apiDelete).toHaveBeenCalledWith('/cart-items/item-4/')
  })
})
