<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { apiGet } from '@/api/http'
import type { ContentPage } from '@/api/types'

const props = defineProps<{ slug: string }>()

const page = ref<ContentPage | null>(null)
const error = ref('')
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ''
  try {
    page.value = await apiGet<ContentPage>(`/pages/${props.slug}/`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '页面加载失败'
    page.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.slug, load)
onMounted(load)
</script>

<template>
  <div class="container">
    <section class="section">
      <div v-if="loading" class="skeleton" style="height: 220px" />
      <div v-else-if="error" class="empty">{{ error }}</div>
      <article v-else-if="page" class="panel">
        <h1 style="margin: 0 0 16px; font-size: 22px">{{ page.title }}</h1>
        <p style="line-height: 1.9; color: #303743; margin: 0">{{ page.body }}</p>
      </article>
    </section>
  </div>
</template>
