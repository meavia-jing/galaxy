<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiGet } from '@/api/http'
import type { Banner, PageResult, ProductSummary } from '@/api/types'
import HeroBanner from '@/components/HeroBanner.vue'
import ProductCard from '@/components/ProductCard.vue'

const banners = ref<Banner[]>([])
const featured = ref<ProductSummary[]>([])
const latest = ref<ProductSummary[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [bannerData, featuredData, latestData] = await Promise.all([
      apiGet<Banner[]>('/banners/'),
      apiGet<PageResult<ProductSummary>>('/products/', { sort: 'newest', page_size: 4 }),
      apiGet<PageResult<ProductSummary>>('/products/', { sort: 'newest', page_size: 8 }),
    ])
    banners.value = bannerData
    featured.value = featuredData.items.filter((item) => item.is_featured).slice(0, 4)
    latest.value = latestData.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="container">
    <HeroBanner v-if="banners.length" :banners="banners" />

    <div v-else-if="loading" class="hero skeleton" style="min-height: 320px" />

    <p v-if="error" class="error-text" style="margin-top: 20px">
      {{ error }}
      <button class="btn btn--ghost" style="margin-left: 10px" @click="load">重试</button>
    </p>

    <section class="section">
      <div class="section__head">
        <h2 class="section__title">精选推荐</h2>
        <span class="section__hint">运营精选 · 限时好价</span>
      </div>
      <div v-if="loading" class="grid">
        <div v-for="n in 4" :key="n" class="skeleton" style="height: 300px" />
      </div>
      <div v-else-if="featured.length" class="grid">
        <ProductCard v-for="item in featured" :key="item.id" :product="item" />
      </div>
      <div v-else class="empty">暂无推荐商品</div>
    </section>

    <section class="section">
      <div class="section__head">
        <h2 class="section__title">全部新品</h2>
        <RouterLink to="/products" class="section__hint">查看全部 →</RouterLink>
      </div>
      <div v-if="loading" class="grid">
        <div v-for="n in 8" :key="n" class="skeleton" style="height: 300px" />
      </div>
      <div v-else-if="latest.length" class="grid">
        <ProductCard v-for="item in latest" :key="item.id" :product="item" />
      </div>
      <div v-else class="empty">暂无商品</div>
    </section>
  </div>
</template>
