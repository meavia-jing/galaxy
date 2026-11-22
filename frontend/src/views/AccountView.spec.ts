import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { UserProfile } from '@/api/types'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPatch: vi.fn(),
  apiPost: vi.fn(),
  ensureCsrf: vi.fn(),
  setAccessToken: vi.fn(),
  push: vi.fn(),
  route: { query: {} as Record<string, string> },
}))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return {
    ...actual,
    apiGet: mocks.apiGet,
    apiPatch: mocks.apiPatch,
    apiPost: mocks.apiPost,
    ensureCsrf: mocks.ensureCsrf,
    setAccessToken: mocks.setAccessToken,
  }
})

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => mocks.route,
}))

import { ApiRequestError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import AccountView from '@/views/AccountView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

function profile(overrides: Partial<UserProfile> = {}): UserProfile {
  return {
    id: '1',
    username: 'demo',
    nickname: '演示用户',
    email: 'demo@example.com',
    role: 'user',
    must_change_password: false,
    date_joined: '2026-11-01T10:00:00+08:00',
    ...overrides,
  }
}

async function mountView() {
  const wrapper = mount(AccountView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  mocks.apiGet.mockReset().mockResolvedValue(profile())
  mocks.apiPatch.mockReset()
  mocks.apiPost.mockReset().mockResolvedValue({})
  mocks.ensureCsrf.mockReset().mockResolvedValue(undefined)
  mocks.setAccessToken.mockReset()
  mocks.push.mockReset()
  mocks.route.query = {}
})

describe('AccountView', () => {
  it('[UNIT-FE-22][I02-T05] 加载资料并提交昵称/邮箱白名单字段', async () => {
    mocks.apiPatch.mockResolvedValue(profile({ nickname: '新昵称' }))
    const wrapper = await mountView()

    expect((wrapper.get('input[maxlength="50"]').element as HTMLInputElement).value).toBe('演示用户')
    expect((wrapper.get('input[type="email"]').element as HTMLInputElement).value).toBe(
      'demo@example.com',
    )

    await wrapper.get('input[maxlength="50"]').setValue('新昵称')
    await wrapper.findAll('button').find((btn) => btn.text() === '保存资料')?.trigger('click')
    await flushPromises()

    expect(mocks.apiPatch).toHaveBeenCalledWith('/users/me/', {
      nickname: '新昵称',
      email: 'demo@example.com',
    })
    expect(wrapper.text()).toContain('资料已保存')
  })

  it('[UNIT-FE-23][I02-T05] 两次新密码不一致时前端拦截，不发请求', async () => {
    const wrapper = await mountView()

    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('ShopDemo2026')
    await inputs[1].setValue('FreshPass2026x')
    await inputs[2].setValue('Different2026x')
    await wrapper.findAll('button').find((btn) => btn.text() === '修改密码')?.trigger('click')
    await flushPromises()

    expect(mocks.apiPost).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('两次输入的新密码不一致')
  })

  it('[UNIT-FE-24][I02-T05] 服务端字段错误回填到改密区域', async () => {
    mocks.apiPost.mockRejectedValue(
      new ApiRequestError({
        code: 'INVALID_REQUEST',
        message: '参数校验失败',
        fields: { old_password: '原密码不正确' },
      }),
    )
    const wrapper = await mountView()

    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('wrong-password')
    await inputs[1].setValue('FreshPass2026x')
    await inputs[2].setValue('FreshPass2026x')
    await wrapper.findAll('button').find((btn) => btn.text() === '修改密码')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('原密码不正确')
  })

  it('[UNIT-FE-25][I02-T05] 临时密码用户被强制改密，成功后恢复资料区', async () => {
    mocks.route.query = { force: '1' }
    mocks.apiGet.mockResolvedValue(profile({ must_change_password: true }))
    mocks.apiPost.mockResolvedValue({
      access: 'new-access',
      user: profile({ must_change_password: false }),
    })

    const wrapper = await mountView()
    expect(wrapper.text()).toContain('管理员已重置你的密码')
    expect(wrapper.find('input[maxlength="50"]').exists()).toBe(false)

    const inputs = wrapper.findAll('input[type="password"]')
    await inputs[0].setValue('TempPass2026x')
    await inputs[1].setValue('FreshPass2026x')
    await inputs[2].setValue('FreshPass2026x')
    await wrapper.findAll('button').find((btn) => btn.text() === '修改密码')?.trigger('click')
    await flushPromises()

    expect(mocks.apiPost).toHaveBeenCalledWith('/users/me/change-password/', {
      old_password: 'TempPass2026x',
      new_password: 'FreshPass2026x',
    })
    expect(mocks.setAccessToken).toHaveBeenCalledWith('new-access')
    expect(wrapper.text()).toContain('密码已修改，其他设备已下线')
    expect(wrapper.find('input[maxlength="50"]').exists()).toBe(true)
  })

  it('[UNIT-FE-26][I02-T05] 退出登录清空内存态并回到首页', async () => {
    const auth = useAuthStore()
    auth.user = profile()
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '退出登录')?.trigger('click')
    await flushPromises()

    expect(mocks.apiPost).toHaveBeenCalledWith('/auth/logout/')
    expect(auth.user).toBeNull()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'home' })
  })
})
