<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { addToCart } from '@/api/cart'
import { apiGet, ApiRequestError } from '@/api/http'
import { formatPrice, type ProductDetail, type Sku } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{ id: string }>()

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const product = ref<ProductDetail | null>(null)
const selectedSkuId = ref('')
const loading = ref(true)
const error = ref('')
const cartQuantity = ref(1)
const adding = ref(false)
const addError = ref('')
const added = ref('')

const selectedSku = computed<Sku | null>(
  () => product.value?.skus.find((sku) => sku.id === selectedSkuId.value) ?? null,
)

const inStock = computed(() => (selectedSku.value?.stock_available ?? 0) > 0)

const specKey = computed(() => {
  const attrs = selectedSku.value?.attributes ?? {}
  return Object.entries(attrs)
    .map(([key, value]) => `${key}：${value}`)
    .join(' · ')
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiGet<ProductDetail>(`/products/${props.id}/`)
    product.value = data
    selectedSkuId.value = data.skus[0]?.id ?? ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : '商品加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function clampQuantity(): void {
  const value = Number(cartQuantity.value)
  const max = selectedSku.value?.stock_available ?? 1
  // 前端先收敛到 1..min(99, 库存)，避免把明显非法值发给服务端；最终以服务端为准。
  if (!Number.isFinite(value)) cartQuantity.value = 1
  else cartQuantity.value = Math.min(Math.max(Math.trunc(value), 1), Math.min(99, Math.max(max, 1)))
}

async function addCurrentSku(): Promise<void> {
  addError.value = ''
  added.value = ''
  if (!selectedSku.value) {
    addError.value = '请先选择规格'
    return
  }
  // 未登录先送去登录页，并带上回跳地址，避免加购动作凭空消失。
  if (!auth.isLoggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  clampQuantity()
  adding.value = true
  try {
    await addToCart(selectedSku.value.id, cartQuantity.value)
    added.value = `已加入购物车（${cartQuantity.value} 件）`
  } catch (err) {
    addError.value = err instanceof ApiRequestError ? err.message : '加入购物车失败，请稍后重试'
  } finally {
    adding.value = false
  }
}
</script>

<template>
  <div class="container">
    <div v-if="loading" class="product-layout">
      <div class="skeleton" style="height: 420px" />
      <div class="skeleton" style="height: 420px" />
    </div>

    <div v-else-if="error" class="empty" style="margin-top: 24px">
      {{ error }}
      <div style="margin-top: 12px">
        <RouterLink to="/products" class="btn">返回商品列表</RouterLink>
      </div>
    </div>

    <template v-else-if="product">
      <nav style="margin-top: 20px; font-size: 13px; color: var(--muted)">
        <RouterLink to="/">首页</RouterLink> /
        <RouterLink to="/products">全部商品</RouterLink> /
        <span>{{ product.title }}</span>
      </nav>

      <div class="product-layout">
        <div class="product-gallery">
          <img
            v-if="product.cover_image"
            :src="product.cover_image"
            :alt="product.title"
          />
        </div>

        <div class="panel">
          <span class="badge">{{ product.category_name }}</span>
          <h1 style="font-size: 24px; margin: 12px 0 6px">{{ product.title }}</h1>
          <p style="color: var(--muted); margin: 0 0 18px">{{ product.subtitle }}</p>

          <div style="background: #f8f9fd; border-radius: 12px; padding: 16px 18px; margin-bottom: 18px">
            <div class="price" style="font-size: 28px">
              ¥{{ formatPrice(selectedSku?.price ?? product.price_min) }}
            </div>
            <div style="font-size: 12.5px; color: var(--muted); margin-top: 4px">
              库存 {{ selectedSku?.stock_available ?? 0 }} 件 · 顺丰包邮
            </div>
          </div>

          <div v-if="product.skus.length > 1">
            <div style="font-size: 13px; color: var(--muted)">选择规格</div>
            <div class="spec-list">
              <button
                v-for="sku in product.skus"
                :key="sku.id"
                class="spec"
                :class="{ 'spec--active': sku.id === selectedSkuId }"
                type="button"
                @click="selectedSkuId = sku.id"
              >
                {{
                  Object.values(sku.attributes)
                    .map((value) => `${value}`)
                    .join(' ') || sku.sku_code
                }}
              </button>
            </div>
            <p style="font-size: 12.5px; color: var(--muted); margin: 10px 0 0">
              {{ specKey }}
            </p>
          </div>

          <div class="notice" style="margin-top: 18px">
            下单与支付将在后续迭代（I04-T02/T03、I05）开放；当前可加入购物车，不会产生订单或扣款。
          </div>

          <div v-if="inStock" class="buy-row">
            <label class="buy-row__qty">
              <span>数量</span>
              <input
                v-model.number="cartQuantity"
                class="input buy-row__input"
                type="number"
                min="1"
                max="99"
                aria-label="购买数量"
                @blur="clampQuantity"
              />
            </label>
          </div>

          <p v-if="added" class="buy-message buy-message--ok" role="status">
            {{ added }}
            <RouterLink :to="{ name: 'cart' }" class="buy-message__link">去购物车结算</RouterLink>
          </p>
          <p v-if="addError" class="error-text buy-message" role="alert">{{ addError }}</p>

          <div style="display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap">
            <button class="btn" type="button" :disabled="adding || !inStock" @click="addCurrentSku">
              {{ adding ? '加入中…' : inStock ? '加入购物车' : '暂时缺货' }}
            </button>
            <RouterLink to="/products" class="btn btn--ghost">继续逛逛</RouterLink>
          </div>
        </div>
      </div>

      <section class="section">
        <div class="section__head">
          <h2 class="section__title">商品详情</h2>
        </div>
        <div class="panel" style="line-height: 1.9; color: #303743">
          {{ product.description }}
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.buy-row {
  margin-top: 16px;
}

.buy-row__qty {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--muted);
}

.buy-row__input {
  width: 88px;
  height: 36px;
  text-align: center;
}

.buy-message {
  margin: 12px 0 0;
  font-size: 13px;
}

.buy-message--ok {
  color: #12805c;
}

.buy-message__link {
  margin-left: 8px;
  color: var(--brand);
}
</style>
