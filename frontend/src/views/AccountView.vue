<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiRequestError, apiGet, apiPatch, ensureCsrf } from '@/api/http'
import type { UserProfile } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const profile = ref<UserProfile | null>(null)
const form = ref({ nickname: '', email: '' })
const message = ref('')
const error = ref('')
const saving = ref(false)

onMounted(async () => {
  profile.value = await apiGet<UserProfile>('/users/me/').catch(() => null)
  if (profile.value) {
    form.value.nickname = profile.value.nickname
    form.value.email = profile.value.email
  }
})

async function save() {
  error.value = ''
  message.value = ''
  saving.value = true
  try {
    await ensureCsrf()
    const updated = await apiPatch<UserProfile>('/users/me/', form.value)
    profile.value = updated
    if (auth.user) auth.user = { ...auth.user, ...updated }
    message.value = '资料已保存'
  } catch (err) {
    if (err instanceof ApiRequestError) {
      error.value = Object.values(err.fields)[0] || err.message
    } else {
      error.value = '保存失败'
    }
  } finally {
    saving.value = false
  }
}

async function logout() {
  await auth.logout()
  router.push({ name: 'home' })
}
</script>

<template>
  <div class="container">
    <div class="section__head" style="margin-top: 26px">
      <h2 class="section__title">个人中心</h2>
      <span class="section__hint">资料与账号安全</span>
    </div>

    <div class="panel" style="max-width: 620px">
      <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 22px">
        <div
          style="width: 52px; height: 52px; border-radius: 50%; background: linear-gradient(135deg,#2f6bff,#7aa2ff); color: #fff; display: grid; place-items: center; font-size: 20px; font-weight: 700"
        >
          {{ (profile?.nickname || profile?.username || 'U').slice(0, 1).toUpperCase() }}
        </div>
        <div>
          <div style="font-weight: 600">{{ profile?.nickname || profile?.username }}</div>
          <div style="font-size: 12.5px; color: var(--muted)">
            {{ profile?.username }} · 角色 {{ profile?.role }}
          </div>
        </div>
      </div>

      <label class="field">
        <span>昵称</span>
        <input v-model="form.nickname" class="input" maxlength="50" />
      </label>
      <label class="field">
        <span>邮箱</span>
        <input v-model="form.email" class="input" type="email" />
      </label>

      <p v-if="message" style="color: #12805c; font-size: 13px; margin: 0 0 12px">{{ message }}</p>
      <p v-if="error" class="error-text" style="margin: 0 0 12px">{{ error }}</p>

      <div style="display: flex; gap: 10px">
        <button class="btn" type="button" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存资料' }}
        </button>
        <button class="btn btn--ghost" type="button" @click="logout">退出登录</button>
      </div>

      <div class="notice" style="margin-top: 22px">
        地址管理、订单与交易记录将在 I04/I05 迭代开放；当前迭代仅包含资料编辑与登录态管理。
      </div>
    </div>
  </div>
</template>
