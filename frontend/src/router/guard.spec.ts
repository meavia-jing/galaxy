import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UserProfile } from '@/api/types'

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return {
    ...actual,
    apiGet: vi.fn(),
    apiPost: vi.fn(),
    ensureCsrf: vi.fn().mockResolvedValue(undefined),
    refreshAccessToken: vi.fn().mockResolvedValue(null),
  }
})

import { setAccessToken } from '@/api/http'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const profile: UserProfile = {
  id: '1',
  username: 'demo',
  nickname: '',
  email: '',
  role: 'user',
  must_change_password: false,
  date_joined: '2026-11-15T00:00:00Z',
}

beforeEach(async () => {
  setActivePinia(createPinia())
  setAccessToken(null)
  const auth = useAuthStore()
  auth.initialized = true
  auth.user = null
})

describe('路由守卫', () => {
  it('[UNIT-FE-08][I02-T05] 未登录访问 /account 重定向到 /login', async () => {
    await router.push('/account')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/account')
  })

  it('[UNIT-FE-09][I02-T05] 已登录访问 /login 重定向到首页', async () => {
    const auth = useAuthStore()
    auth.user = profile
    setAccessToken('access-1')

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('[UNIT-FE-09][I02-T05] 未登录访问公开页不跳转', async () => {
    await router.push('/products')

    expect(router.currentRoute.value.name).toBe('products')
  })
})
