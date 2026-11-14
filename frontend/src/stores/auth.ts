import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  ApiRequestError,
  apiGet,
  apiPost,
  ensureCsrf,
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
} from '@/api/http'
import type { UserProfile } from '@/api/types'

interface LoginPayload {
  access: string
  user: UserProfile
  must_change_password?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserProfile | null>(null)
  const initializing = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value && getAccessToken()))
  const displayName = computed(() => user.value?.nickname || user.value?.username || '')

  /** Restore the session on page reload using the HttpOnly refresh cookie. */
  async function bootstrap(): Promise<void> {
    if (initialized.value || initializing.value) return
    initializing.value = true
    try {
      await ensureCsrf()
      const token = await refreshAccessToken()
      if (token) {
        user.value = await apiGet<UserProfile>('/users/me/').catch(() => null)
        if (!user.value) setAccessToken(null)
      }
    } finally {
      initializing.value = false
      initialized.value = true
    }
  }

  async function login(username: string, password: string): Promise<LoginPayload> {
    await ensureCsrf()
    const payload = await apiPost<LoginPayload>('/auth/login/', { username, password })
    setAccessToken(payload.access)
    user.value = payload.user
    initialized.value = true
    return payload
  }

  async function register(form: {
    username: string
    password: string
    nickname?: string
    email?: string
  }): Promise<void> {
    await ensureCsrf()
    const payload = await apiPost<LoginPayload>('/auth/register/', form)
    setAccessToken(payload.access)
    user.value = payload.user
    initialized.value = true
  }

  async function logout(): Promise<void> {
    try {
      await apiPost('/auth/logout/')
    } catch (error) {
      if (!(error instanceof ApiRequestError)) throw error
    } finally {
      setAccessToken(null)
      user.value = null
    }
  }

  return {
    user,
    isLoggedIn,
    displayName,
    initializing,
    initialized,
    bootstrap,
    login,
    register,
    logout,
  }
})
