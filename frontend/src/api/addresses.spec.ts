import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
}))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return { ...actual, ...mocks }
})

import {
  createAddress,
  fetchAddresses,
  removeAddress,
  setDefaultAddress,
  updateAddress,
} from '@/api/addresses'
import type { AddressPayload } from '@/api/types'

const payload: AddressPayload = {
  recipient: '张三',
  phone: '13800138000',
  province: '北京市',
  city: '北京市',
  district: '朝阳区',
  detail: '建国路 88 号 1 单元 101',
  is_default: false,
}

beforeEach(() => {
  mocks.apiGet.mockReset().mockResolvedValue([])
  mocks.apiPost.mockReset().mockResolvedValue({ id: '1', ...payload })
  mocks.apiPatch.mockReset().mockResolvedValue({ id: '9', ...payload })
  mocks.apiDelete.mockReset().mockResolvedValue(undefined)
})

describe('addresses API', () => {
  it('[UNIT-FE-16][I02-T05] 列表请求打到 /addresses/', async () => {
    await fetchAddresses()
    expect(mocks.apiGet).toHaveBeenCalledWith('/addresses/')
  })

  it('[UNIT-FE-17][I02-T05] 新增地址以 POST 提交完整载荷', async () => {
    await createAddress(payload)
    expect(mocks.apiPost).toHaveBeenCalledWith('/addresses/', payload)
  })

  it('[UNIT-FE-18][I02-T05] 编辑地址以 PATCH 提交到带 id 的地址', async () => {
    await updateAddress('9', { detail: '新地址 1 号' })
    expect(mocks.apiPatch).toHaveBeenCalledWith('/addresses/9/', { detail: '新地址 1 号' })
  })

  it('[UNIT-FE-20][I02-T05] 设默认只提交 is_default 一个字段', async () => {
    await setDefaultAddress('9')
    expect(mocks.apiPatch).toHaveBeenCalledWith('/addresses/9/', { is_default: true })
  })

  it('[UNIT-FE-19][I02-T05] 删除地址走 DELETE', async () => {
    await removeAddress('9')
    expect(mocks.apiDelete).toHaveBeenCalledWith('/addresses/9/')
  })
})
