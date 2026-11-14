<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { Banner } from '@/api/types'

const props = defineProps<{ banners: Banner[] }>()

const current = ref(0)
let timer: number | undefined

function start() {
  stop()
  if (props.banners.length > 1) {
    timer = window.setInterval(() => {
      current.value = (current.value + 1) % props.banners.length
    }, 5000)
  }
}

function stop() {
  if (timer) window.clearInterval(timer)
  timer = undefined
}

watch(
  () => props.banners.length,
  () => {
    current.value = 0
    start()
  },
)

onMounted(start)
onBeforeUnmount(stop)
</script>

<template>
  <div v-if="banners.length" class="hero">
    <img
      class="hero__image"
      :src="banners[current].image_path"
      :alt="banners[current].title"
    />
    <div class="hero__overlay">
      <span class="badge">限时活动</span>
      <h1 class="hero__title">{{ banners[current].title }}</h1>
      <p class="hero__subtitle">品质好物 · 顺丰包邮 · 7 天无理由退换</p>
      <div style="display: flex; gap: 10px; margin-top: 6px">
        <RouterLink :to="banners[current].target_url || '/products'" class="btn">
          立即选购
        </RouterLink>
        <RouterLink to="/pages/help" class="btn btn--ghost" style="color: #fff; border-color: rgba(255,255,255,.4)">
          了解详情
        </RouterLink>
      </div>
    </div>
  </div>
</template>
