import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UserProfile } from '@/api/types'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  ensureCsrf: vi.fn(),
  refreshAccessToken: vi.fn(),
}))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return {
    ...actual,
    apiGet: mocks.apiGet,
    apiPost: mocks.apiPost,
    ensureCsrf: mocks.ensureCsrf,
    refreshAccessToken: mocks.refreshAccessToken,
  }
})

import { ApiRequestError, getAccessToken, setAccessToken } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const profile: UserProfile = {
  id: '1',
  username: 'demo',
  nickname: '演示用户',
  email: '',
  role: 'user',
  must_change_password: false,
  date_joined: '2026-11-15T00:00:00Z',
}

beforeEach(() => {
  setActivePinia(createPinia())
  setAccessToken(null)
  mocks.apiGet.mockReset()
  mocks.apiPost.mockReset()
  mocks.ensureCsrf.mockReset().mockResolvedValue(undefined)
  mocks.refreshAccessToken.mockReset()
})

describe('auth store', () => {
  it('[UNIT-FE-03][I02-T05] 登录成功后写入 user 与内存 access', async () => {
    mocks.apiPost.mockResolvedValue({ access: 'access-1', user: profile })
    const auth = useAuthStore()

    await auth.login('demo', 'ShopDemo2026')

    expect(getAccessToken()).toBe('access-1')
    expect(auth.isLoggedIn).toBe(true)
    expect(auth.displayName).toBe('演示用户')
    expect(mocks.ensureCsrf).toHaveBeenCalledTimes(1)
  })

  it('[UNIT-FE-04][I02-T05] bootstrap 无有效 Cookie 时保持未登录', async () => {
    mocks.refreshAccessToken.mockResolvedValue(null)
    const auth = useAuthStore()

    await expect(auth.bootstrap()).resolves.toBeUndefined()

    expect(auth.initialized).toBe(true)
    expect(auth.initializing).toBe(false)
    expect(auth.isLoggedIn).toBe(false)
    expect(getAccessToken()).toBeNull()
  })

  it('[UNIT-FE-04][I02-T05] bootstrap 有 refresh 时恢复 user', async () => {
    mocks.refreshAccessToken.mockImplementation(async () => {
      setAccessToken('restored-token')
      return 'restored-token'
    })
    mocks.apiGet.mockResolvedValue(profile)
    const auth = useAuthStore()

    await auth.bootstrap()

    expect(auth.isLoggedIn).toBe(true)
    expect(auth.user?.username).toBe('demo')
  })

  it('[UNIT-FE-05][I02-T05] 登出清空内存态，业务错误不外抛', async () => {
    mocks.apiPost.mockResolvedValue({ access: 'access-1', user: profile })
    const auth = useAuthStore()
    await auth.login('demo', 'ShopDemo2026')
    expect(auth.isLoggedIn).toBe(true)

    mocks.apiPost.mockRejectedValue(
      new ApiRequestError({ code: 'UNAUTHORIZED', message: '登录状态已失效' }),
    )

    await expect(auth.logout()).resolves.toBeUndefined()
    expect(auth.user).toBeNull()
    expect(getAccessToken()).toBeNull()
    expect(auth.isLoggedIn).toBe(false)
  })
})
