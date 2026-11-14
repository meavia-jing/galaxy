<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiRequestError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = ref({ username: '', nickname: '', email: '', password: '', confirm: '' })
const error = ref('')
const submitting = ref(false)

async function submit() {
  error.value = ''
  if (!/^[a-z0-9_]{4,32}$/.test(form.value.username.trim().toLowerCase())) {
    error.value = '用户名需为 4-32 位小写字母、数字或下划线'
    return
  }
  if (form.value.password.length < 10) {
    error.value = '密码至少 10 位'
    return
  }
  if (form.value.password !== form.value.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  submitting.value = true
  try {
    await auth.register({
      username: form.value.username.trim().toLowerCase(),
      password: form.value.password,
      nickname: form.value.nickname,
      email: form.value.email,
    })
    router.push({ name: 'home' })
  } catch (err) {
    if (err instanceof ApiRequestError) {
      const firstField = Object.values(err.fields)[0]
      error.value = firstField || err.message
    } else {
      error.value = '注册失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-wrap">
    <form class="auth-card" @submit.prevent="submit">
      <h1 style="margin: 0 0 6px; font-size: 22px">注册</h1>
      <p style="margin: 0 0 22px; color: var(--muted); font-size: 13px">
        创建账号以使用购物车、订单与个人中心。
      </p>

      <label class="field">
        <span>用户名（4-32 位小写字母、数字、下划线）</span>
        <input v-model="form.username" class="input" autocomplete="username" />
      </label>
      <label class="field">
        <span>昵称（可选）</span>
        <input v-model="form.nickname" class="input" maxlength="50" />
      </label>
      <label class="field">
        <span>邮箱（可选）</span>
        <input v-model="form.email" class="input" type="email" autocomplete="email" />
      </label>
      <label class="field">
        <span>密码（至少 10 位）</span>
        <input v-model="form.password" class="input" type="password" autocomplete="new-password" />
      </label>
      <label class="field">
        <span>确认密码</span>
        <input v-model="form.confirm" class="input" type="password" autocomplete="new-password" />
      </label>

      <p v-if="error" class="error-text" style="margin: 0 0 12px">{{ error }}</p>

      <button class="btn" style="width: 100%; height: 42px" type="submit" :disabled="submitting">
        {{ submitting ? '提交中…' : '注册并登录' }}
      </button>

      <p style="margin: 16px 0 0; font-size: 13px; color: var(--muted); text-align: center">
        已有账号？
        <RouterLink to="/login" style="color: var(--brand)">去登录</RouterLink>
      </p>
    </form>
  </div>
</template>
