<script setup>
defineProps({ title: { type: String, required: true }, desc: { type: String, default: '' }, readonly: Boolean })
</script>

<template>
  <div class="ph">
    <h2>{{ title }}</h2>
    <span v-if="desc" class="desc">{{ desc }}</span>
    <span v-if="readonly" class="readonly-badge">조회 전용</span>
  </div>
</template>
