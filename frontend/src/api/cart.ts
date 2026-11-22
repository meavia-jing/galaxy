import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/http'
import type { CartItem, CartSummary } from '@/api/types'

/** 后端 `cart.urls`：`/api/v1/cart-items/` 与 `/api/v1/cart/`。 */
const ITEMS = '/cart-items/'

/** 汇总接口同时返回列表、可结算小计和不可用标记，一次请求够用。 */
export function fetchCart(): Promise<CartSummary> {
  return apiGet<CartSummary>('/cart/')
}

export function fetchCartItems(): Promise<CartItem[]> {
  return apiGet<CartItem[]>(ITEMS)
}

/** 数量按「设置为指定值」传，不是增量；同 SKU 由服务端合并为一行。 */
export function addToCart(
  skuId: string,
  quantity: number,
  selected = true,
): Promise<CartItem> {
  return apiPost<CartItem>(ITEMS, { sku_id: skuId, quantity, selected })
}

export function updateCartItem(
  id: string,
  payload: { quantity?: number; selected?: boolean },
): Promise<CartItem> {
  return apiPatch<CartItem>(`${ITEMS}${id}/`, payload)
}

export function removeCartItem(id: string): Promise<void> {
  return apiDelete<void>(`${ITEMS}${id}/`)
}
