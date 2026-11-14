<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { apiGet } from '@/api/http'
import { formatPrice, type ProductDetail, type Sku } from '@/api/types'

const props = defineProps<{ id: string }>()

const product = ref<ProductDetail | null>(null)
const selectedSkuId = ref('')
const loading = ref(true)
const error = ref('')

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
            购物车与下单功能将在下一迭代（I04）开放；当前仅展示商品信息与规格价格。
          </div>

          <div style="display: flex; gap: 10px; margin-top: 18px">
            <button class="btn" type="button" disabled>
              {{ inStock ? '加入购物车（即将开放）' : '暂时缺货' }}
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
