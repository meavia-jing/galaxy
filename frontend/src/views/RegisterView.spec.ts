import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  register: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ register: mocks.register }),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return { ...actual, useRouter: () => ({ push: mocks.push }) }
})

import { ApiRequestError } from '@/api/http'
import RegisterView from '@/views/RegisterView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

async function fillAndSubmit(wrapper: ReturnType<typeof mount>) {
  const inputs = wrapper.findAll('input')
  await inputs[0].setValue('new_user')
  await inputs[3].setValue('StrongPass2026')
  await inputs[4].setValue('StrongPass2026')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  mocks.register.mockReset()
  mocks.push.mockReset()
})

describe('RegisterView', () => {
  it('[UNIT-FE-10][I01-T03] 后端字段错误优先作为提示文案', async () => {
    mocks.register.mockRejectedValue(
      new ApiRequestError({
        code: 'INVALID_REQUEST',
        message: '请求参数不正确',
        fields: { password: '该密码太常见了' },
      }),
    )

    const wrapper = mount(RegisterView, { global: { stubs } })
    await fillAndSubmit(wrapper)

    expect(wrapper.get('.error-text').text()).toBe('该密码太常见了')
  })

  it('[UNIT-FE-10][I01-T03] 无字段错误时回落到 message', async () => {
    mocks.register.mockRejectedValue(
      new ApiRequestError({ code: 'CONFLICT', message: '服务繁忙，请稍后再试' }),
    )

    const wrapper = mount(RegisterView, { global: { stubs } })
    await fillAndSubmit(wrapper)

    expect(wrapper.get('.error-text').text()).toBe('服务繁忙，请稍后再试')
  })

  it('[UNIT-FE-10][I02-T01] 前端先拦截两次密码不一致', async () => {
    const wrapper = mount(RegisterView, { global: { stubs } })
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('new_user')
    await inputs[3].setValue('StrongPass2026')
    await inputs[4].setValue('AnotherPass2026')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('.error-text').text()).toBe('两次输入的密码不一致')
    expect(mocks.register).not.toHaveBeenCalled()
  })
})
