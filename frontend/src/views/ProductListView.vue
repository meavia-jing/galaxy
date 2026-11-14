<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { apiGet } from '@/api/http'
import type { Category, PageResult, ProductSummary } from '@/api/types'
import ProductCard from '@/components/ProductCard.vue'

const route = useRoute()
const router = useRouter()

const categories = ref<Category[]>([])
const products = ref<ProductSummary[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref('')

const keyword = ref(String(route.query.keyword ?? ''))
const sort = ref(String(route.query.sort ?? 'newest'))
const page = ref(Number(route.query.page ?? 1))

const sorts = [
  { value: 'newest', label: '最新' },
  { value: 'price_asc', label: '价格从低到高' },
  { value: 'price_desc', label: '价格从高到低' },
]

const activeCategory = computed(() => String(route.query.category ?? ''))
const totalPages = computed(() => Math.max(Math.ceil(total.value / 20), 1))

async function loadCategories() {
  try {
    categories.value = await apiGet<Category[]>('/categories/')
  } catch {
    categories.value = []
  }
}

async function loadProducts() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiGet<PageResult<ProductSummary>>('/products/', {
      category: activeCategory.value || undefined,
      keyword: keyword.value || undefined,
      sort: sort.value,
      page: page.value,
      page_size: 20,
    })
    products.value = data.items
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    products.value = []
  } finally {
    loading.value = false
  }
}

function syncQuery(patch: Record<string, string | number | undefined>) {
  const query = { ...route.query, ...patch }
  Object.keys(query).forEach((key) => {
    if (query[key] === '' || query[key] === undefined) delete query[key]
  })
  router.push({ name: 'products', query })
}

function selectCategory(slug: string) {
  syncQuery({ category: slug, page: 1 })
}

function submitSearch() {
  syncQuery({ keyword: keyword.value, page: 1 })
}

function changeSort(value: string) {
  sort.value = value
  syncQuery({ sort: value, page: 1 })
}

watch(
  () => route.query,
  (query) => {
    keyword.value = String(query.keyword ?? '')
    sort.value = String(query.sort ?? 'newest')
    page.value = Number(query.page ?? 1)
    loadProducts()
  },
)

onMounted(async () => {
  await loadCategories()
  await loadProducts()
})
</script>

<template>
  <div class="container">
    <div class="section__head" style="margin-top: 26px">
      <h2 class="section__title">全部商品</h2>
      <span class="section__hint">共 {{ total }} 件商品</span>
    </div>

    <div class="toolbar">
      <button
        class="chip"
        :class="{ 'chip--active': !activeCategory }"
        type="button"
        @click="selectCategory('')"
      >
        全部
      </button>
      <button
        v-for="category in categories"
        :key="category.id"
        class="chip"
        :class="{ 'chip--active': activeCategory === category.slug }"
        type="button"
        @click="selectCategory(category.slug)"
      >
        {{ category.name }}
      </button>

      <div style="display: flex; gap: 8px; margin-left: auto">
        <input
          v-model="keyword"
          class="input"
          type="search"
          placeholder="搜索商品名称"
          @keyup.enter="submitSearch"
        />
        <button class="btn btn--ghost" type="button" @click="submitSearch">搜索</button>
      </div>
    </div>

    <div class="toolbar" style="margin-top: -6px">
      <span style="font-size: 13px; color: var(--muted)">排序：</span>
      <button
        v-for="item in sorts"
        :key="item.value"
        class="chip"
        :class="{ 'chip--active': sort === item.value }"
        type="button"
        @click="changeSort(item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div v-if="loading" class="grid">
      <div v-for="n in 8" :key="n" class="skeleton" style="height: 300px" />
    </div>
    <div v-else-if="error" class="empty">
      {{ error }}
      <div style="margin-top: 12px">
        <button class="btn" type="button" @click="loadProducts">重新加载</button>
      </div>
    </div>
    <div v-else-if="products.length" class="grid">
      <ProductCard v-for="item in products" :key="item.id" :product="item" />
    </div>
    <div v-else class="empty">没有符合条件的商品，试试其他关键词或分类。</div>

    <div v-if="!loading && totalPages > 1" class="pager">
      <button
        class="btn btn--ghost"
        type="button"
        :disabled="page <= 1"
        @click="syncQuery({ page: page - 1 })"
      >
        上一页
      </button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button
        class="btn btn--ghost"
        type="button"
        :disabled="page >= totalPages"
        @click="syncQuery({ page: page + 1 })"
      >
        下一页
      </button>
    </div>
  </div>
</template>
