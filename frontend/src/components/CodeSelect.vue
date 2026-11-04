<script setup>
import { computed } from 'vue'
import { session } from '../stores/session'

const props = defineProps({
  modelValue: { type: String, default: '' },
  group: { type: String, required: true },
  empty: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
const options = computed(() => session.codes?.[props.group] ?? [])
</script>

<template>
  <select :value="modelValue ?? ''" @change="$emit('update:modelValue', $event.target.value)">
    <option v-if="empty" value="">{{ empty }}</option>
    <option v-for="item in options" :key="item.code" :value="item.code">{{ item.name }}</option>
  </select>
</template>
