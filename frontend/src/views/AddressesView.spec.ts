import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError } from '@/api/http'
import type { Address } from '@/api/types'

const mocks = vi.hoisted(() => ({
  fetchAddresses: vi.fn(),
  createAddress: vi.fn(),
  updateAddress: vi.fn(),
  removeAddress: vi.fn(),
  setDefaultAddress: vi.fn(),
}))

vi.mock('@/api/addresses', () => mocks)

import AddressesView from '@/views/AddressesView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

function address(overrides: Partial<Address> = {}): Address {
  return {
    id: '1',
    recipient: '张三',
    phone: '13800138000',
    province: '北京市',
    city: '北京市',
    district: '朝阳区',
    detail: '建国路 88 号 1 单元 101',
    is_default: false,
    created_at: '2026-11-01T10:00:00+08:00',
    updated_at: '2026-11-01T10:00:00+08:00',
    ...overrides,
  }
}

async function mountView() {
  const wrapper = mount(AddressesView, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  mocks.fetchAddresses.mockReset().mockResolvedValue([])
  mocks.createAddress.mockReset()
  mocks.updateAddress.mockReset()
  mocks.removeAddress.mockReset()
  mocks.setDefaultAddress.mockReset()
})

describe('AddressesView', () => {
  it('[UNIT-FE-16][I02-T05] 渲染地址列表并只标记一个默认地址', async () => {
    mocks.fetchAddresses.mockResolvedValue([
      address({ id: '1', is_default: true }),
      address({ id: '2', recipient: '李四', is_default: false }),
    ])

    const wrapper = await mountView()

    expect(wrapper.findAll('.addr-card')).toHaveLength(2)
    expect(wrapper.findAll('.addr-badge')).toHaveLength(1)
    expect(wrapper.get('.addr-badge').text()).toBe('默认')
    // 默认地址不再显示「设为默认」
    expect(wrapper.findAll('button').filter((btn) => btn.text() === '设为默认')).toHaveLength(1)
    expect(wrapper.text()).toContain('建国路 88 号')
  })

  it('[UNIT-FE-16][I02-T05] 无地址时显示空态', async () => {
    const wrapper = await mountView()
    expect(wrapper.find('.empty').text()).toContain('还没有收货地址')
  })

  it('[UNIT-FE-16][I02-T05] 加载失败展示错误并可重试', async () => {
    mocks.fetchAddresses.mockRejectedValueOnce(new Error('后端不可用'))

    const wrapper = await mountView()
    expect(wrapper.find('.empty').text()).toContain('后端不可用')

    const retry = wrapper.findAll('button').find((btn) => btn.text() === '重新加载')
    await retry?.trigger('click')
    await flushPromises()

    expect(mocks.fetchAddresses).toHaveBeenCalledTimes(2)
  })

  it('[UNIT-FE-17][I02-T05] 新增地址提交后重新拉取列表并提示', async () => {
    mocks.createAddress.mockResolvedValue(address({ id: '3' }))
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '新增地址')?.trigger('click')
    await wrapper.get('input[name="recipient"]').setValue('王五')
    await wrapper.get('input[name="phone"]').setValue('13900139000')
    await wrapper.get('input[name="province"]').setValue('上海市')
    await wrapper.get('input[name="city"]').setValue('上海市')
    await wrapper.get('input[name="district"]').setValue('浦东新区')
    await wrapper.get('input[name="detail"]').setValue('世纪大道 1 号')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.createAddress).toHaveBeenCalledWith({
      recipient: '王五',
      phone: '13900139000',
      province: '上海市',
      city: '上海市',
      district: '浦东新区',
      detail: '世纪大道 1 号',
      is_default: false,
    })
    expect(mocks.fetchAddresses).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('地址已添加')
    expect(wrapper.find('.addr-form').exists()).toBe(false)
  })

  it('[UNIT-FE-21][I02-T05] 必填项为空时前端拦截，不发请求', async () => {
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '新增地址')?.trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.createAddress).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请填写收件人')
    expect(wrapper.text()).toContain('请填写详细地址')
  })

  it('[UNIT-FE-21][I02-T05] 服务端字段错误回填到表单，总览不再重复同一句', async () => {
    mocks.createAddress.mockRejectedValue(
      new ApiRequestError({
        code: 'VALIDATION_ERROR',
        message: '参数校验失败',
        fields: { phone: '请填写正确的手机号或固话（如 13800138000 / 010-12345678）' },
      }),
    )
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '新增地址')?.trigger('click')
    await wrapper.get('input[name="recipient"]').setValue('赵六')
    await wrapper.get('input[name="phone"]').setValue('1234567')
    await wrapper.get('input[name="province"]').setValue('广东省')
    await wrapper.get('input[name="city"]').setValue('深圳市')
    await wrapper.get('input[name="district"]').setValue('南山区')
    await wrapper.get('input[name="detail"]').setValue('科技园 2 号')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    // 字段级提示只出现在 phone 输入框下方
    const inline = wrapper.findAll('.addr-form .error-text')
    expect(inline).toHaveLength(1)
    expect(inline[0].text()).toContain('请填写正确的手机号或固话')
    // 顶部总览只给一句概括，不重复字段文案
    expect(wrapper.get('.addr-message').text()).toBe('请修正表单中标红的字段后重试')
    expect(wrapper.find('.addr-form').exists()).toBe(true)
  })

  it('[UNIT-FE-20][I02-T05] 点击设默认调用对应地址', async () => {
    mocks.fetchAddresses.mockResolvedValue([address({ id: '2' })])
    const wrapper = await mountView()

    await wrapper.findAll('button').find((btn) => btn.text() === '设为默认')?.trigger('click')
    await flushPromises()

    expect(mocks.setDefaultAddress).toHaveBeenCalledWith('2')
    expect(wrapper.text()).toContain('默认地址已切换')
  })

  it('[UNIT-FE-19][I02-T05] 删除需确认，确认后调用删除并刷新', async () => {
    mocks.fetchAddresses.mockResolvedValue([address({ id: '5' })])
    mocks.removeAddress.mockResolvedValue(undefined)
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

    const wrapper = await mountView()
    await wrapper.findAll('button').find((btn) => btn.text() === '删除')?.trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(mocks.removeAddress).toHaveBeenCalledWith('5')
    expect(wrapper.text()).toContain('地址已删除')
    confirmSpy.mockRestore()
  })

  it('[UNIT-FE-19][I02-T05] 取消确认时不删除', async () => {
    mocks.fetchAddresses.mockResolvedValue([address({ id: '5' })])
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

    const wrapper = await mountView()
    await wrapper.findAll('button').find((btn) => btn.text() === '删除')?.trigger('click')
    await flushPromises()

    expect(mocks.removeAddress).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('[UNIT-FE-18][I02-T05] 编辑表单预填原值并以 PATCH 提交', async () => {
    mocks.fetchAddresses.mockResolvedValue([address({ id: '7', recipient: '孙七' })])
    mocks.updateAddress.mockResolvedValue(address({ id: '7', recipient: '孙七' }))

    const wrapper = await mountView()
    await wrapper.findAll('button').find((btn) => btn.text() === '编辑')?.trigger('click')

    expect((wrapper.get('input[name="recipient"]').element as HTMLInputElement).value).toBe('孙七')

    await wrapper.get('input[name="detail"]').setValue('新地址 9 号')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.updateAddress).toHaveBeenCalledWith('7', expect.objectContaining({ detail: '新地址 9 号' }))
    expect(wrapper.text()).toContain('地址已更新')
  })
})
