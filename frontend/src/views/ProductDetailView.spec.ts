import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProductDetail } from '@/api/types'

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  addToCart: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@/api/http', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/http')>()
  return { ...actual, apiGet: mocks.apiGet }
})

vi.mock('@/api/cart', () => ({ addToCart: mocks.addToCart }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRouter: () => ({ push: mocks.push }),
    useRoute: () => ({ fullPath: '/products/1' }),
  }
})

import ProductDetailView from '@/views/ProductDetailView.vue'
import { ApiRequestError, setAccessToken } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

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

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(ProductDetailView, {
    props: { id: '1' },
    global: { plugins: [pinia], stubs },
  })
}

/** 已登录态：store 的 isLoggedIn 同时要求 user 与内存 access。 */
function signIn() {
  const auth = useAuthStore()
  auth.user = {
    id: '1',
    username: 'demo',
    nickname: '演示用户',
    email: '',
    role: 'user',
    must_change_password: false,
    date_joined: '2026-11-01T10:00:00+08:00',
  }
  setAccessToken('test-access')
}

beforeEach(() => {
  mocks.apiGet.mockReset()
  mocks.apiGet.mockResolvedValue(detail)
  mocks.addToCart.mockReset().mockResolvedValue({})
  mocks.push.mockReset()
  setAccessToken(null)
})

describe('ProductDetailView', () => {
  it('[UNIT-FE-11][I03-T03] 切换 SKU 联动价格与库存', async () => {
    const wrapper = mountView()
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

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.empty').text()).toContain('商品加载失败')
  })

  it('[UNIT-FE-39][I04-T01] 未登录点击加购跳登录页并带 redirect', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('button').find((btn) => btn.text() === '加入购物车')?.trigger('click')
    await flushPromises()

    expect(mocks.push).toHaveBeenCalledWith({
      name: 'login',
      query: { redirect: '/products/1' },
    })
    expect(mocks.addToCart).not.toHaveBeenCalled()
  })

  it('[UNIT-FE-40][I04-T01] 登录后加购按当前 SKU 与数量提交', async () => {
    const wrapper = mountView()
    await flushPromises()
    signIn()

    const qty = wrapper.get('input[type="number"]')
    await qty.setValue('3')
    await wrapper.findAll('button').find((btn) => btn.text() === '加入购物车')?.trigger('click')
    await flushPromises()

    expect(mocks.addToCart).toHaveBeenCalledWith('sku-1', 3)
    expect(wrapper.get('.buy-message--ok').text()).toContain('已加入购物车（3 件）')
  })

  it('[UNIT-FE-41][I04-T01] 数量按库存收敛，避免提交超过库存的值', async () => {
    const wrapper = mountView()
    await flushPromises()
    signIn()

    const qty = wrapper.get('input[type="number"]')
    await qty.setValue('99')
    await qty.trigger('blur')
    await wrapper.findAll('button').find((btn) => btn.text() === '加入购物车')?.trigger('click')
    await flushPromises()

    // 当前 SKU 库存 5，前端应收敛到 5 而不是把 99 发出去。
    expect(mocks.addToCart).toHaveBeenCalledWith('sku-1', 5)
  })

  it('[UNIT-FE-42][I04-T01] 加购失败展示服务端消息', async () => {
    mocks.addToCart.mockRejectedValue(
      new ApiRequestError({ code: 'SKU_UNAVAILABLE', message: '该商品已下架，无法加入购物车' }),
    )
    const wrapper = mountView()
    await flushPromises()
    signIn()

    await wrapper.findAll('button').find((btn) => btn.text() === '加入购物车')?.trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toBe('该商品已下架，无法加入购物车')
  })
})
