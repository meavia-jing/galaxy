<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { createAddress, fetchAddresses, removeAddress, setDefaultAddress, updateAddress } from '@/api/addresses'
import { ApiRequestError } from '@/api/http'
import type { Address, AddressPayload } from '@/api/types'
import AddressForm from '@/components/AddressForm.vue'

const addresses = ref<Address[]>([])
const loading = ref(true)
const loadError = ref('')
const creating = ref(false)
const editing = ref<Address | null>(null)
const saving = ref(false)
const formErrors = ref<Record<string, string>>({})
const message = ref('')
const actionError = ref('')

const formOpen = computed(() => creating.value || editing.value !== null)
const formInitial = computed<Partial<AddressPayload> | null>(() => editing.value)

const REQUIRED: Array<[keyof AddressPayload, string]> = [
  ['recipient', '请填写收件人'],
  ['phone', '请填写联系电话'],
  ['province', '请填写省'],
  ['city', '请填写市'],
  ['district', '请填写区/县'],
  ['detail', '请填写详细地址'],
]

function validate(payload: AddressPayload): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const [field, text] of REQUIRED) {
    if (!String(payload[field] ?? '').trim()) errors[field] = text
  }
  // 后端 PHONE_RE 同时接受手机与固话，这里只做长度与数字的粗筛，最终以服务端为准。
  const phone = payload.phone.trim()
  if (phone && !/^[\d-]{6,20}$/.test(phone)) {
    errors.phone = '请填写正确的手机号或固话（如 13800138000 / 010-12345678）'
  }
  return errors
}

function describe(err: unknown, fallback: string): string {
  if (err instanceof ApiRequestError) {
    return Object.values(err.fields)[0] || err.message || fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}

function fieldErrors(err: unknown): Record<string, string> {
  return err instanceof ApiRequestError ? err.fields : {}
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    addresses.value = await fetchAddresses()
  } catch (err) {
    loadError.value = describe(err, '地址加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(load)

function closeForm(): void {
  creating.value = false
  editing.value = null
  formErrors.value = {}
}

function startCreate(): void {
  creating.value = true
  editing.value = null
  formErrors.value = {}
  message.value = ''
  actionError.value = ''
}

function startEdit(address: Address): void {
  editing.value = address
  creating.value = false
  formErrors.value = {}
  message.value = ''
  actionError.value = ''
}

async function save(payload: AddressPayload): Promise<void> {
  formErrors.value = validate(payload)
  actionError.value = ''
  if (Object.keys(formErrors.value).length) return

  saving.value = true
  const wasEditing = editing.value !== null
  try {
    if (editing.value) {
      await updateAddress(editing.value.id, payload)
    } else {
      await createAddress(payload)
    }
    closeForm()
    await load()
    message.value = wasEditing ? '地址已更新' : '地址已添加'
  } catch (err) {
    const fields = fieldErrors(err)
    formErrors.value = fields
    // 字段错误已经写在对应输入框下方，这里只给一句总览，避免同一句话重复两遍。
    actionError.value = Object.keys(fields).length
      ? '请修正表单中标红的字段后重试'
      : describe(err, '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

async function makeDefault(address: Address): Promise<void> {
  if (address.is_default) return
  actionError.value = ''
  try {
    await setDefaultAddress(address.id)
    await load()
    message.value = '默认地址已切换'
  } catch (err) {
    actionError.value = describe(err, '切换默认地址失败')
  }
}

async function remove(address: Address): Promise<void> {
  if (!window.confirm(`确定删除「${address.recipient}」的收货地址？`)) return
  actionError.value = ''
  try {
    await removeAddress(address.id)
    if (editing.value?.id === address.id) closeForm()
    await load()
    message.value = '地址已删除'
  } catch (err) {
    actionError.value = describe(err, '删除失败，请稍后重试')
  }
}

function fullAddress(address: Address): string {
  return `${address.province}${address.city}${address.district}${address.detail}`
}
</script>

<template>
  <div class="container">
    <div class="section__head" style="margin-top: 26px">
      <h2 class="section__title">收货地址</h2>
      <span class="section__hint">最多 20 条，仅本人可见</span>
    </div>

    <p v-if="message" class="addr-message" role="status">{{ message }}</p>
    <p v-if="actionError" class="error-text addr-message" role="alert">{{ actionError }}</p>

    <div style="display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap">
      <button class="btn" type="button" @click="startCreate">新增地址</button>
      <RouterLink class="btn btn--ghost" :to="{ name: 'account' }">返回个人中心</RouterLink>
    </div>

    <div v-if="formOpen" class="panel" style="margin-bottom: 18px">
      <h3 style="margin: 0 0 14px; font-size: 16px">{{ editing ? '编辑地址' : '新增地址' }}</h3>
      <AddressForm
        :initial="formInitial"
        :submitting="saving"
        :errors="formErrors"
        @submit="save"
        @cancel="closeForm"
      />
    </div>

    <div v-if="loading" class="addr-list">
      <div v-for="n in 2" :key="n" class="panel skeleton" style="height: 132px" />
    </div>

    <div v-else-if="loadError" class="empty">
      <p style="margin: 0 0 12px">{{ loadError }}</p>
      <button class="btn btn--ghost" type="button" @click="load">重新加载</button>
    </div>

    <div v-else-if="!addresses.length" class="empty">
      <p style="margin: 0 0 6px">还没有收货地址</p>
      <p style="margin: 0; font-size: 13px">添加后可在结算时直接选用。</p>
    </div>

    <div v-else class="addr-list">
      <article v-for="address in addresses" :key="address.id" class="panel addr-card">
        <div class="addr-card__head">
          <strong>{{ address.recipient }}</strong>
          <span v-if="address.is_default" class="addr-badge">默认</span>
          <span class="addr-card__phone">{{ address.phone }}</span>
        </div>
        <p class="addr-card__text">{{ fullAddress(address) }}</p>
        <div class="addr-card__actions">
          <button
            v-if="!address.is_default"
            class="btn btn--ghost"
            type="button"
            @click="makeDefault(address)"
          >
            设为默认
          </button>
          <button class="btn btn--ghost" type="button" @click="startEdit(address)">编辑</button>
          <button class="btn btn--ghost" type="button" @click="remove(address)">删除</button>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.addr-message {
  margin: 0 0 12px;
  font-size: 13px;
  color: #12805c;
}

.addr-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.addr-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 15px;
}

.addr-card__phone {
  font-size: 13px;
  color: var(--muted);
}

.addr-card__text {
  margin: 10px 0 14px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text);
  word-break: break-all;
}

.addr-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.addr-card__actions .btn {
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
}

.addr-badge {
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(47, 107, 255, 0.1);
  color: var(--brand);
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 390px) {
  .addr-list {
    grid-template-columns: 1fr;
  }

  .addr-card__actions .btn {
    flex: 1 1 auto;
    height: 38px;
  }
}
</style>
