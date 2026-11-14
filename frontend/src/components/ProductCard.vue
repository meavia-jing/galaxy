<script setup lang="ts">
import { computed } from 'vue'

import { formatPrice, type ProductSummary } from '@/api/types'

const props = defineProps<{ product: ProductSummary }>()

const priceLabel = computed(() => {
  const min = formatPrice(props.product.price_min)
  const max = formatPrice(props.product.price_max)
  return min === max ? `¥${min}` : `¥${min} 起`
})
</script>

<template>
  <RouterLink :to="`/products/${product.id}`" class="card">
    <div class="card__media">
      <img
        v-if="product.cover_image"
        :src="product.cover_image"
        :alt="product.title"
        loading="lazy"
      />
    </div>
    <div class="card__body">
      <div class="card__title">{{ product.title }}</div>
      <div class="card__meta">{{ product.subtitle }}</div>
      <div style="margin-top: auto; display: flex; align-items: center; justify-content: space-between">
        <span class="price">{{ priceLabel }}</span>
        <span class="badge">{{ product.category_name }}</span>
      </div>
    </div>
  </RouterLink>
</template>
