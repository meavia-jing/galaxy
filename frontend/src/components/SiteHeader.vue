<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const greeting = computed(() =>
  auth.displayName ? `你好，${auth.displayName}` : '',
)

async function handleLogout() {
  await auth.logout()
  router.push({ name: 'home' })
}
</script>

<template>
  <header class="site-header">
    <div class="container site-header__bar">
      <RouterLink to="/" class="logo">
        <span class="logo__mark">云</span>
        <span>云集商城</span>
      </RouterLink>

      <nav class="nav">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/products">全部商品</RouterLink>
        <RouterLink to="/pages/help">帮助中心</RouterLink>
      </nav>

      <div class="header-actions">
        <template v-if="auth.isLoggedIn">
          <span style="color: var(--muted)">{{ greeting }}</span>
          <RouterLink to="/account" class="btn btn--ghost">个人中心</RouterLink>
          <button class="btn" type="button" @click="handleLogout">退出</button>
        </template>
        <template v-else>
          <RouterLink to="/login" class="btn btn--ghost">登录</RouterLink>
          <RouterLink to="/register" class="btn">注册</RouterLink>
        </template>
      </div>
    </div>
  </header>
</template>
