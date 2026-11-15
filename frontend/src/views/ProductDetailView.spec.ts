import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProductDetail } from '@/api/types'

const mocks = vi.hoisted(() => ({ apiGet: vi.fn() }))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return { ...actual, apiGet: mocks.apiGet }
})

import ProductDetailView from '@/views/ProductDetailView.vue'

const detail: ProductDetail = {
  id: '1',
  title: '云集蓝牙耳机',
  slug: 'earbuds',
  subtitle: '主动降噪',
  category_id: '1',
  category_name: '数码',
  price_min: '10.00',
  price_max: '25.00',
  cover_image: '',
  is_featured: false,
  description: '商品详情正文',
  images: [],
  skus: [
    {
      id: 'sku-1',
      sku_code: 'EAR-BLACK',
      attributes: { 颜色: '黑色' },
      price: '10.00',
      stock_available: 5,
      is_active: true,
    },
    {
      id: 'sku-2',
      sku_code: 'EAR-WHITE',
      attributes: { 颜色: '白色' },
      price: '25.00',
      stock_available: 3,
      is_active: true,
    },
  ],
}

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

beforeEach(() => {
  mocks.apiGet.mockReset()
  mocks.apiGet.mockResolvedValue(detail)
})

describe('ProductDetailView', () => {
  it('[UNIT-FE-11][I03-T03] 切换 SKU 联动价格与库存', async () => {
    const wrapper = mount(ProductDetailView, {
      props: { id: '1' },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.get('.price').text()).toBe('¥10.00')
    expect(wrapper.text()).toContain('库存 5 件')

    const specs = wrapper.findAll('.spec')
    expect(specs).toHaveLength(2)

    await specs[1].trigger('click')

    expect(wrapper.get('.price').text()).toBe('¥25.00')
    expect(wrapper.text()).toContain('库存 3 件')
    expect(wrapper.text()).toContain('颜色：白色')
  })

  it('[UNIT-FE-11][I03-T03] 加载失败显示错误与返回入口', async () => {
    mocks.apiGet.mockRejectedValue(new Error('商品加载失败'))

    const wrapper = mount(ProductDetailView, {
      props: { id: '1' },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.find('.empty').text()).toContain('商品加载失败')
  })
})
