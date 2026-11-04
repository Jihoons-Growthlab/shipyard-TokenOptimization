<script setup>
import { toasts } from '../stores/toast'
</script>

<template>
  <div class="toasts" aria-live="polite">
    <div v-for="item in toasts" :key="item.id" class="toast" :class="item.type">{{ item.message }}</div>
  </div>
</template>
