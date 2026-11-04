<script setup>
import { computed } from 'vue'

const props = defineProps({ items: { type: Array, required: true } })
const NAMES = { PLAN: '계획', READY: '착수가능', WORK: '진행', DONE: '완료', DELAY: '지연' }
const RADIUS = 40
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const total = computed(() => props.items.reduce((sum, item) => sum + item.count, 0))
const arcs = computed(() => {
  let offset = 0
  return props.items.filter((item) => item.count).map((item) => {
    const length = (item.count / total.value) * CIRCUMFERENCE
    const arc = { status: item.status, dash: `${length} ${CIRCUMFERENCE - length}`, offset: -offset }
    offset += length
    return arc
  })
})
</script>

<template>
  <div class="wrap">
    <svg width="120" height="120" viewBox="0 0 120 120" role="img" aria-label="공정 상태 분포">
      <g transform="rotate(-90 60 60)">
        <circle cx="60" cy="60" :r="RADIUS" fill="none" stroke="#e5e7eb" stroke-width="22" />
        <circle
          v-for="arc in arcs" :key="arc.status" cx="60" cy="60" :r="RADIUS" fill="none" stroke-width="22"
          :stroke="`var(--c-${arc.status})`" :stroke-dasharray="arc.dash" :stroke-dashoffset="arc.offset"
        />
      </g>
      <text x="60" y="62" text-anchor="middle" class="sum">{{ total }}</text>
      <text x="60" y="76" text-anchor="middle" class="lbl">전체</text>
    </svg>
    <ul>
      <li v-for="item in items" :key="item.status"><i :style="{ background: `var(--c-${item.status})` }" />{{ NAMES[item.status] }} <b>{{ item.count }}</b></li>
    </ul>
  </div>
</template>

<style scoped>
.wrap { display: flex; align-items: center; gap: 18px; padding-left: 0; }
.sum { font-size: 20px; font-weight: 700; fill: var(--navy); }
.lbl { font-size: 10px; fill: var(--muted); }
ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 7px; font-size: 12px; }
li { display: flex; align-items: center; gap: 6px; }
li i { width: 10px; height: 10px; border-radius: 2px; }
</style>
