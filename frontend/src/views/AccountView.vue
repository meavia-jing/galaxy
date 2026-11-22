<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ApiRequestError,
  apiGet,
  apiPatch,
  apiPost,
  ensureCsrf,
  setAccessToken,
} from '@/api/http'
import type { UserProfile } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const profile = ref<UserProfile | null>(null)
const form = ref({ nickname: '', email: '' })
const message = ref('')
const error = ref('')
const saving = ref(false)

// 管理员重置临时密码后，前端只开放改密与退出；force=1 来自登录跳转。
const forced = ref(route.query.force === '1')
const mustChange = computed(
  () => forced.value || Boolean(profile.value?.must_change_password),
)
const passwordForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const passwordMessage = ref('')
const passwordError = ref('')
const changing = ref(false)

onMounted(async () => {
  profile.value = await apiGet<UserProfile>('/users/me/').catch(() => null)
  if (profile.value) {
    form.value.nickname = profile.value.nickname
    form.value.email = profile.value.email
    if (profile.value.must_change_password) forced.value = true
  }
})

async function save() {
  if (mustChange.value) return
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

async function changePassword() {
  passwordError.value = ''
  passwordMessage.value = ''
  const { old_password, new_password, confirm_password } = passwordForm.value
  if (!old_password || !new_password) {
    passwordError.value = '请填写原密码与新密码'
    return
  }
  if (new_password.length < 10) {
    passwordError.value = '新密码至少 10 位'
    return
  }
  if (new_password !== confirm_password) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  changing.value = true
  try {
    await ensureCsrf()
    const result = await apiPost<{ access: string; user: UserProfile }>(
      '/users/me/change-password/',
      { old_password, new_password },
    )
    setAccessToken(result.access)
    profile.value = result.user
    auth.user = result.user
    forced.value = false
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    passwordMessage.value = '密码已修改，其他设备已下线'
  } catch (err) {
    if (err instanceof ApiRequestError) {
      const field = Object.values(err.fields)[0]
      passwordError.value = field || err.message
    } else {
      passwordError.value = '修改密码失败，请稍后重试'
    }
  } finally {
    changing.value = false
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

      <div v-if="mustChange" class="notice" role="alert" style="margin-bottom: 20px">
        管理员已重置你的密码。请先在下方设置新密码；修改成功前仅可访问本页与退出登录。
      </div>

      <template v-if="!mustChange">
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

        <div style="display: flex; gap: 10px; flex-wrap: wrap">
          <button class="btn" type="button" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存资料' }}
          </button>
          <RouterLink class="btn btn--ghost" :to="{ name: 'addresses' }">管理收货地址</RouterLink>
        </div>
      </template>

      <div style="border-top: 1px solid var(--line); margin: 22px 0 18px" />

      <h3 style="margin: 0 0 12px; font-size: 16px">
        {{ mustChange ? '设置新密码（必须）' : '修改密码' }}
      </h3>
      <label class="field">
        <span>原密码</span>
        <input
          v-model="passwordForm.old_password"
          class="input"
          type="password"
          autocomplete="current-password"
        />
      </label>
      <label class="field">
        <span>新密码（至少 10 位）</span>
        <input
          v-model="passwordForm.new_password"
          class="input"
          type="password"
          autocomplete="new-password"
        />
      </label>
      <label class="field">
        <span>确认新密码</span>
        <input
          v-model="passwordForm.confirm_password"
          class="input"
          type="password"
          autocomplete="new-password"
        />
      </label>

      <p v-if="passwordMessage" style="color: #12805c; font-size: 13px; margin: 0 0 12px">
        {{ passwordMessage }}
      </p>
      <p v-if="passwordError" class="error-text" style="margin: 0 0 12px">{{ passwordError }}</p>

      <div style="display: flex; gap: 10px; flex-wrap: wrap">
        <button class="btn" type="button" :disabled="changing" @click="changePassword">
          {{ changing ? '提交中…' : '修改密码' }}
        </button>
        <button class="btn btn--ghost" type="button" @click="logout">退出登录</button>
      </div>

      <div v-if="!mustChange" class="notice" style="margin-top: 22px">
        订单与交易记录将在 I04/I05 迭代开放；当前可用资料编辑、收货地址管理与登录态管理。
      </div>
    </div>
  </div>
</template>
