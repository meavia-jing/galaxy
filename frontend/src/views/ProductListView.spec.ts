import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProductSummary } from '@/api/types'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  route: { query: {} as Record<string, string> },
  push: vi.fn(),
}))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return { ...actual, apiGet: mocks.apiGet }
})

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mocks.route,
    useRouter: () => ({ push: mocks.push }),
  }
})

import ProductListView from '@/views/ProductListView.vue'

const stubs = { RouterLink: { template: '<a><slot /></a>' } }

const item: ProductSummary = {
  id: '1',
  title: '云集蓝牙耳机',
  slug: 'earbuds',
  subtitle: '',
  category_id: '1',
  category_name: '数码',
  price_min: '199.00',
  price_max: '199.00',
  cover_image: '',
  is_featured: false,
}

function mockCatalog(products: ProductSummary[], total: number) {
  mocks.apiGet.mockImplementation((url: string) => {
    if (url === '/categories/') return Promise.resolve([])
    return Promise.resolve({ items: products, page: 1, page_size: 20, total })
  })
}

beforeEach(() => {
  mocks.apiGet.mockReset()
  mocks.push.mockReset()
  mocks.route.query = {}
})

describe('ProductListView', () => {
  it('[UNIT-FE-13][I03-T03] 首次加载渲染 8 个骨架占位', async () => {
    mocks.apiGet.mockReturnValue(new Promise(() => undefined))

    const wrapper = mount(ProductListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.findAll('.skeleton')).toHaveLength(8)
  })

  it('[UNIT-FE-12][I03-T03] 空结果显示空态文案', async () => {
    mockCatalog([], 0)

    const wrapper = mount(ProductListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.empty').text()).toContain('没有符合条件的商品')
    expect(wrapper.findAll('.skeleton')).toHaveLength(0)
  })

  it('[UNIT-FE-14][I03-T03] 请求失败显示错误并可重试', async () => {
    mocks.apiGet.mockImplementation((url: string) => {
      if (url === '/categories/') return Promise.resolve([])
      return Promise.reject(new Error('后端不可用'))
    })

    const wrapper = mount(ProductListView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('.empty').text()).toContain('后端不可用')
    const calls = mocks.apiGet.mock.calls.length
    const retry = wrapper.findAll('button').find((btn) => btn.text() === '重新加载')
    expect(retry).toBeTruthy()

    await retry?.trigger('click')
    await flushPromises()

    expect(mocks.apiGet.mock.calls.length).toBeGreaterThan(calls)
  })

  it('[UNIT-FE-15][I03-T02] 首页禁用「上一页」，点击「下一页」写入 query', async () => {
    mockCatalog([item], 40)

    const wrapper = mount(ProductListView, { global: { stubs } })
    await flushPromises()

    const [prev, next] = wrapper.get('.pager').findAll('button')
    expect(prev.attributes('disabled')).toBeDefined()
    expect(next.attributes('disabled')).toBeUndefined()

    await next.trigger('click')
    expect(mocks.push).toHaveBeenCalledWith({ name: 'products', query: { page: 2 } })
  })

  it('[UNIT-FE-15][I03-T02] 末页禁用「下一页」', async () => {
    mocks.route.query = { page: '2' }
    mockCatalog([item], 40)

    const wrapper = mount(ProductListView, { global: { stubs } })
    await flushPromises()

    const [prev, next] = wrapper.get('.pager').findAll('button')
    expect(prev.attributes('disabled')).toBeUndefined()
    expect(next.attributes('disabled')).toBeDefined()
  })
})
