<script setup lang="ts">
import { reactive, watch } from 'vue'

import type { AddressPayload } from '@/api/types'

const props = defineProps<{
  initial?: Partial<AddressPayload> | null
  submitting?: boolean
  errors?: Record<string, string>
}>()

const emit = defineEmits<{ submit: [AddressPayload]; cancel: [] }>()

function emptyForm(): AddressPayload {
  return {
    recipient: '',
    phone: '',
    province: '',
    city: '',
    district: '',
    detail: '',
    is_default: false,
  }
}

const form = reactive<AddressPayload>(emptyForm())

watch(
  () => props.initial,
  (value) => {
    Object.assign(form, emptyForm(), {
      recipient: value?.recipient ?? '',
      phone: value?.phone ?? '',
      province: value?.province ?? '',
      city: value?.city ?? '',
      district: value?.district ?? '',
      detail: value?.detail ?? '',
      is_default: value?.is_default ?? false,
    })
  },
  { immediate: true },
)

function fieldError(name: keyof AddressPayload): string {
  return props.errors?.[name] ?? ''
}

function onSubmit(): void {
  emit('submit', { ...form })
}
</script>

<template>
  <form class="addr-form" @submit.prevent="onSubmit">
    <label class="field">
      <span>收件人</span>
      <input v-model="form.recipient" class="input" name="recipient" maxlength="50" />
      <small v-if="fieldError('recipient')" class="error-text">{{ fieldError('recipient') }}</small>
    </label>

    <label class="field">
      <span>联系电话</span>
      <input v-model="form.phone" class="input" name="phone" maxlength="20" placeholder="13800138000 或 010-12345678" />
      <small v-if="fieldError('phone')" class="error-text">{{ fieldError('phone') }}</small>
    </label>

    <div class="addr-form__row">
      <label class="field">
        <span>省</span>
        <input v-model="form.province" class="input" name="province" maxlength="50" />
        <small v-if="fieldError('province')" class="error-text">{{ fieldError('province') }}</small>
      </label>
      <label class="field">
        <span>市</span>
        <input v-model="form.city" class="input" name="city" maxlength="50" />
        <small v-if="fieldError('city')" class="error-text">{{ fieldError('city') }}</small>
      </label>
      <label class="field">
        <span>区/县</span>
        <input v-model="form.district" class="input" name="district" maxlength="50" />
        <small v-if="fieldError('district')" class="error-text">{{ fieldError('district') }}</small>
      </label>
    </div>

    <label class="field">
      <span>详细地址</span>
      <input v-model="form.detail" class="input" name="detail" maxlength="200" />
      <small v-if="fieldError('detail')" class="error-text">{{ fieldError('detail') }}</small>
    </label>

    <label class="addr-form__check">
      <input v-model="form.is_default" type="checkbox" name="is_default" />
      <span>设为默认地址</span>
    </label>

    <div class="addr-form__actions">
      <button class="btn" type="submit" :disabled="submitting">
        {{ submitting ? '保存中…' : '保存地址' }}
      </button>
      <button class="btn btn--ghost" type="button" @click="emit('cancel')">取消</button>
    </div>
  </form>
</template>

<style scoped>
.addr-form__row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.addr-form__row .field {
  flex: 1 1 120px;
  min-width: 0;
}

.addr-form__check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 16px;
}

.addr-form__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* 注意：这段样式必须留在 AddressForm.vue 里。父组件 AddressesView 的 scoped 样式
   管不到子组件内部的 `.addr-form__row`，放过去会静默失效。 */
@media (max-width: 390px) {
  .addr-form__row .field {
    flex: 1 1 100%;
  }
}
</style>
