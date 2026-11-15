export interface Category {
  id: string
  name: string
  slug: string
  parent_id: string | number | null
  sort_order: number
}

export interface ProductSummary {
  id: string
  title: string
  slug: string
  subtitle: string
  category_id: string
  category_name: string
  price_min: string
  price_max: string
  cover_image: string
  is_featured: boolean
}

export interface Sku {
  id: string
  sku_code: string
  attributes: Record<string, string>
  price: string
  stock_available: number
  is_active: boolean
}

export interface ProductImage {
  id: string
  path: string
  alt_text: string
  sort_order: number
}

export interface ProductDetail extends ProductSummary {
  description: string
  images: ProductImage[]
  skus: Sku[]
}

export interface Banner {
  id: string
  title: string
  image_path: string
  target_url: string
  sort_order: number
}

export interface ContentPage {
  slug: string
  title: string
  body: string
  published_at: string
}

export interface PageResult<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface UserProfile {
  id: string
  username: string
  nickname: string
  email: string
  role: string
  must_change_password: boolean
  date_joined: string
}

/** 收货地址，字段与 `accounts.AddressSerializer` 对齐。 */
export interface Address {
  id: string
  recipient: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default: boolean
  created_at: string
  updated_at: string
}

export type AddressPayload = Pick<
  Address,
  'recipient' | 'phone' | 'province' | 'city' | 'district' | 'detail' | 'is_default'
>

export const ADDRESS_FIELDS: Array<keyof AddressPayload> = [
  'recipient',
  'phone',
  'province',
  'city',
  'district',
  'detail',
]

export function formatPrice(value: string | number): string {
  const num = typeof value === 'number' ? value : Number.parseFloat(value || '0')
  // 后端返回空串或脏数据时回落到 0.00，避免界面上出现 ¥NaN
  return (Number.isFinite(num) ? num : 0).toFixed(2)
}
