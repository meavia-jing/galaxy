<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchCart, removeCartItem, updateCartItem } from '@/api/cart'
import { ApiRequestError } from '@/api/http'
import { formatPrice } from '@/api/types'
import type { CartItem } from '@/api/types'
import CartItemRow from '@/components/CartItemRow.vue'

const items = ref<CartItem[]>([])
const subtotal = ref('0.00')
const selectedCount = ref(0)
const hasUnavailable = ref(false)
const loading = ref(true)
const loadError = ref('')
const actionError = ref('')
const message = ref('')
const busy = ref('')

const isEmpty = computed(() => !loading.value && !loadError.value && items.value.length === 0)

function describe(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError) {
    return Object.values(err.fields)[0] || err.message || fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const data = await fetchCart()
    items.value = data.items
    subtotal.value = data.subtotal
    selectedCount.value = data.selected_count
    hasUnavailable.value = data.has_unavailable
  } catch (err) {
    loadError.value = describe(err, '购物车加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function run(item: CartItem, action: () => Promise<unknown>, okText: string) {
  actionError.value = ''
  message.value = ''
  busy.value = item.id
  try {
    await action()
    await load()
    message.value = okText
  } catch (err) {
    actionError.value = describe(err, '操作失败，请稍后重试')
  } finally {
    busy.value = ''
  }
}

/** 勾选只决定结算范围，小计始终由服务端重算，前端不自行相加。 */
function toggle(item: CartItem): Promise<void> {
  return run(item, () => updateCartItem(item.id, { selected: !item.selected }), '已更新勾选')
}

function changeQuantity(item: CartItem, value: number): Promise<void> {
  if (!Number.isInteger(value) || value < 1 || value > 99) {
    actionError.value = '数量需在 1 至 99 之间'
    return Promise.resolve()
  }
  if (value === item.quantity) return Promise.resolve()
  return run(item, () => updateCartItem(item.id, { quantity: value }), '数量已更新')
}

function remove(item: CartItem): Promise<void> | void {
  if (!window.confirm(`确定从购物车移除「${item.product_title}」？`)) return
  return run(item, () => removeCartItem(item.id), '已从购物车移除')
}
</script>

<template>
  <div class="container">
    <div class="section__head" style="margin-top: 26px">
      <h2 class="section__title">购物车</h2>
      <span class="section__hint">已选 {{ selectedCount }} 件</span>
    </div>

    <p v-if="message" class="cart-message" role="status">{{ message }}</p>
    <p v-if="actionError" class="error-text cart-message" role="alert">{{ actionError }}</p>

    <div v-if="loading" class="cart-list">
      <div v-for="n in 2" :key="n" class="panel skeleton" style="height: 118px" />
    </div>

    <div v-else-if="loadError" class="empty">
      <p style="margin: 0 0 12px">{{ loadError }}</p>
      <button class="btn btn--ghost" type="button" @click="load">重新加载</button>
    </div>

    <div v-else-if="isEmpty" class="empty">
      <p style="margin: 0 0 6px">购物车还是空的</p>
      <p style="margin: 0 0 14px; font-size: 13px">去商品列表挑几件喜欢的商品吧。</p>
      <RouterLink class="btn" :to="{ name: 'products' }">去逛逛</RouterLink>
    </div>

    <template v-else>
      <div class="cart-list">
        <CartItemRow
          v-for="item in items"
          :key="item.id"
          :item="item"
          :busy="busy === item.id"
          @toggle="toggle(item)"
          @quantity="changeQuantity(item, $event)"
          @remove="remove(item)"
        />
      </div>

      <div class="panel cart-foot">
        <div class="cart-foot__sum">
          <span style="font-size: 13px; color: var(--muted)">已选 {{ selectedCount }} 件，小计</span>
          <strong class="cart-foot__price">¥{{ formatPrice(subtotal) }}</strong>
        </div>
        <RouterLink class="btn btn--ghost" :to="{ name: 'products' }">继续挑选</RouterLink>
      </div>

      <p v-if="hasUnavailable" class="notice" style="margin-top: 14px">
        存在已下架或库存不足的商品，这些项不会计入小计，请先移除或调整数量。
      </p>

      <p class="notice" style="margin-top: 14px">
        结算与下单（I04-T02/T03）尚未开放，本页仅支持购物车维护；此时不会产生任何订单或扣款。
      </p>
    </template>
  </div>
</template>

<style scoped>
.cart-message {
  margin: 0 0 12px;
  font-size: 13px;
}

.cart-message:not(.error-text) {
  color: #12805c;
}

.cart-list {
  display: grid;
  gap: 12px;
}

.cart-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.cart-foot__sum {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.cart-foot__price {
  font-size: 22px;
  color: var(--danger);
}
</style>
