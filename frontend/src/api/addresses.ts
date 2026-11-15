import { apiDelete, apiGet, apiPatch, apiPost } from '@/api/http'
import type { Address, AddressPayload } from '@/api/types'

/** 后端 `accounts.address_urls`：`/api/v1/addresses/`，仅返回当前登录用户的地址。 */
const BASE = '/addresses/'

export function fetchAddresses(): Promise<Address[]> {
  return apiGet<Address[]>(BASE)
}

export function createAddress(payload: AddressPayload): Promise<Address> {
  return apiPost<Address>(BASE, payload)
}

export function updateAddress(
  id: string,
  payload: Partial<AddressPayload>,
): Promise<Address> {
  return apiPatch<Address>(`${BASE}${id}/`, payload)
}

export function removeAddress(id: string): Promise<void> {
  return apiDelete<void>(`${BASE}${id}/`)
}

/** 设默认走同一个 PATCH；服务层负责在事务内取消其它默认项。 */
export function setDefaultAddress(id: string): Promise<Address> {
  return updateAddress(id, { is_default: true })
}
