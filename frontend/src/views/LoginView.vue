<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiRequestError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  submitting.value = true
  try {
    const payload = await auth.login(username.value.trim().toLowerCase(), password.value)
    if (payload.must_change_password) {
      router.push({ name: 'account', query: { force: '1' } })
      return
    }
    const redirect = String(route.query.redirect ?? '/')
    router.push(redirect.startsWith('/') ? redirect : '/')
  } catch (err) {
    error.value = err instanceof ApiRequestError ? err.message : '登录失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <form class="auth-card" @submit.prevent="submit">
      <h1 style="margin: 0 0 6px; font-size: 22px">登录</h1>
      <p style="margin: 0 0 22px; color: var(--muted); font-size: 13px">
        欢迎回来，登录后可管理个人资料与地址。
      </p>

      <label class="field">
        <span>用户名</span>
        <input v-model="username" class="input" autocomplete="username" placeholder="请输入用户名" />
      </label>

      <label class="field">
        <span>密码</span>
        <input
          v-model="password"
          class="input"
          type="password"
          autocomplete="current-password"
          placeholder="请输入密码"
        />
      </label>

      <p v-if="error" class="error-text" style="margin: 0 0 12px">{{ error }}</p>

      <button class="btn" style="width: 100%; height: 42px" type="submit" :disabled="submitting">
        {{ submitting ? '登录中…' : '登录' }}
      </button>

      <p style="margin: 16px 0 0; font-size: 13px; color: var(--muted); text-align: center">
        还没有账号？
        <RouterLink to="/register" style="color: var(--brand)">立即注册</RouterLink>
      </p>
      <p style="margin: 10px 0 0; font-size: 12px; color: var(--muted); text-align: center">
        演示账号 demo / ShopDemo2026
      </p>
    </form>
  </div>
</template>
