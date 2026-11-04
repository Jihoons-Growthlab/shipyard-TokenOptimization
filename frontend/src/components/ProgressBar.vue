<script setup>
defineProps({ value: { type: Number, default: 0 } })
</script>

<template>
  <div class="pbar">
    <div class="fill" :style="{ width: `${Math.min(Math.max(value, 0), 100)}%` }" />
    <span>{{ value }}%</span>
  </div>
</template>

<style scoped>
.pbar { position: relative; height: 16px; border-radius: 8px; background: #e5e7eb; overflow: hidden; min-width: 90px; }
.fill { position: absolute; inset: 0 auto 0 0; background: var(--pri); }
span { position: absolute; inset: 0; text-align: center; font-size: 10.5px; font-weight: 700; line-height: 16px; }
</style>
