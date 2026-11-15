import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { formatPrice, type ProductSummary } from '@/api/types'
import ProductCard from '@/components/ProductCard.vue'

const product: ProductSummary = {
  id: '1',
  title: '云集蓝牙耳机',
  slug: 'earbuds',
  subtitle: '主动降噪',
  category_id: '1',
  category_name: '数码',
  price_min: '199.00',
  price_max: '199.00',
  cover_image: '',
  is_featured: true,
}

function mountCard(item: ProductSummary) {
  return mount(ProductCard, {
    props: { product: item },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

describe('formatPrice', () => {
  it('[UNIT-FE-01][I03-T03] 固定两位小数并补齐位数', () => {
    expect(formatPrice('199.00')).toBe('199.00')
    expect(formatPrice('199')).toBe('199.00')
    expect(formatPrice(8.5)).toBe('8.50')
  })

  it('[UNIT-FE-02][I03-T03] 空值与非法值回落到 0.00，不抛错', () => {
    expect(formatPrice('')).toBe('0.00')
    expect(formatPrice('not-a-price')).toBe('0.00')
    expect(formatPrice(Number.NaN)).toBe('0.00')
  })
})

describe('ProductCard', () => {
  it('[UNIT-FE-01][I03-T03] 同价商品渲染单一价格 ¥199.00', () => {
    const wrapper = mountCard(product)
    expect(wrapper.get('.price').text()).toBe('¥199.00')
    expect(wrapper.text()).toContain('数码')
  })

  it('[UNIT-FE-02][I03-T03] 价格区间渲染「起」，空价格不出现 NaN', () => {
    const ranged = mountCard({ ...product, price_max: '299.00' })
    expect(ranged.get('.price').text()).toBe('¥199.00 起')

    const broken = mountCard({ ...product, price_min: '', price_max: '' })
    expect(broken.get('.price').text()).toBe('¥0.00')
    expect(broken.text()).not.toContain('NaN')
  })
})
