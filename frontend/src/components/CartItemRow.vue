<script setup lang="ts">
import { computed } from 'vue'

import { formatPrice, type CartItem } from '@/api/types'

const props = defineProps<{ item: CartItem; busy?: boolean }>()

const emit = defineEmits<{
  toggle: []
  quantity: [value: number]
  remove: []
}>()

const specText = computed(
  () => Object.values(props.item.attributes ?? {}).join(' ') || props.item.sku_code,
)

/** 输入框提交后不自行保存，交给父组件请求服务端并以返回值为准。 */
function submitQuantity(event: Event): void {
  const input = event.target as HTMLInputElement
  const next = Number.parseInt(input.value, 10)
  if (!Number.isFinite(next)) {
    input.value = String(props.item.quantity)
    return
  }
  emit('quantity', next)
  // 父组件若拒绝该值会把 item.quantity 原样传回；这里先恢复显示，避免输入框停在脏值。
  if (next === props.item.quantity) input.value = String(props.item.quantity)
}

defineExpose({ specText })
</script>

<template>
  <article class="panel cart-row" :class="{ 'cart-row--off': !item.available }">
    <label class="cart-row__check">
      <input
        type="checkbox"
        :checked="item.selected"
        :disabled="!item.available || busy"
        :aria-label="`选择 ${item.product_title}`"
        @change="emit('toggle')"
      />
    </label>

    <div class="cart-row__body">
      <RouterLink class="cart-row__title" :to="`/products/${item.product_id}`">
        {{ item.product_title }}
      </RouterLink>
      <div class="cart-row__meta">
        {{ specText }} · 单价 ¥{{ formatPrice(item.unit_price) }}
      </div>
      <p v-if="!item.available" class="cart-row__warn">{{ item.unavailable_reason }}</p>
    </div>

    <div class="cart-row__qty">
      <input
        class="input cart-row__input"
        type="number"
        min="1"
        max="99"
        :value="item.quantity"
        :disabled="busy"
        :aria-label="`${item.product_title} 数量`"
        @change="submitQuantity"
      />
      <span class="cart-row__stock">库存 {{ item.stock_available }}</span>
    </div>

    <div class="cart-row__amount">¥{{ formatPrice(item.line_amount) }}</div>

    <button class="btn btn--ghost cart-row__remove" type="button" :disabled="busy" @click="emit('remove')">
      移除
    </button>
  </article>
</template>

<style scoped>
.cart-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: 14px;
}

.cart-row--off {
  border: 1px solid rgba(229, 72, 77, 0.35);
}

.cart-row__check input {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.cart-row__body {
  min-width: 0;
}

.cart-row__title {
  font-weight: 600;
  color: var(--text);
  text-decoration: none;
}

.cart-row__title:hover {
  color: var(--brand);
}

.cart-row__meta {
  margin-top: 4px;
  font-size: 12.5px;
  color: var(--muted);
}

.cart-row__warn {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--danger);
}

.cart-row__qty {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.cart-row__input {
  width: 76px;
  height: 34px;
  text-align: center;
}

.cart-row__stock {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.cart-row__amount {
  font-weight: 600;
  color: var(--danger);
  white-space: nowrap;
}

.cart-row__remove {
  height: 32px;
  padding: 0 12px;
  font-size: 13px;
}

/* 小屏单列：勾选/商品一行，数量与金额并排，移除按钮整行，避免横向滚动。 */
@media (max-width: 640px) {
  .cart-row {
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-areas:
      'check body'
      'qty amount'
      'remove remove';
    gap: 10px 12px;
  }

  .cart-row__check {
    grid-area: check;
  }

  .cart-row__body {
    grid-area: body;
  }

  .cart-row__qty {
    grid-area: qty;
    flex-direction: row;
    align-items: center;
    gap: 10px;
  }

  .cart-row__amount {
    grid-area: amount;
    align-self: center;
    justify-self: end;
  }

  .cart-row__remove {
    grid-area: remove;
    width: 100%;
    height: 38px;
  }
}
</style>
