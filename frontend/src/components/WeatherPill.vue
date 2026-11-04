<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api/client'

const REGIONS = ['울산', '거제', '목포']
const REFRESH_MS = 10 * 60 * 1000
const KEY = 'swp_region'

function savedRegion() {
  try {
    const value = localStorage.getItem(KEY)
    return REGIONS.includes(value) ? value : REGIONS[0]
  } catch {
    return REGIONS[0]
  }
}

const region = ref(savedRegion())
const weather = ref(null)
const state = ref('loading')
let latest = 0
let timer

async function load() {
  const seq = ++latest
  if (!weather.value) state.value = 'loading'
  try {
    const result = await api.get('/weather', { query: { region: region.value } })
    if (seq !== latest) return
    weather.value = result
    state.value = 'ready'
  } catch {
    if (seq !== latest) return
    weather.value = null
    state.value = 'failed'
  }
}

function change() {
  try {
    localStorage.setItem(KEY, region.value)
  } catch {
    // 저장 불가 환경에서도 조회는 계속한다
  }
  weather.value = null
  load()
}

const icon = computed(() => {
  const condition = weather.value?.condition ?? ''
  if (condition.includes('맑')) return '☀️'
  if (condition.includes('구름')) return '⛅'
  if (condition.includes('흐')) return '☁️'
  if (condition.includes('눈')) return '❄️'
  if (condition.includes('비')) return '🌧️'
  return '🌤️'
})

onMounted(() => {
  load()
  timer = setInterval(load, REFRESH_MS)
})
onBeforeUnmount(() => {
  latest += 1
  clearInterval(timer)
})
</script>

<template>
  <div class="pill">
    <select v-model="region" aria-label="지역" @change="change">
      <option v-for="name in REGIONS" :key="name" :value="name">{{ name }}</option>
    </select>
    <template v-if="weather">
      <span>{{ icon }}</span>
      <b>{{ weather.tempC.toFixed(1) }}℃</b>
      <span>{{ weather.condition }}</span>
      <span class="sub">습도 {{ weather.humidity }}% · 바람 {{ weather.windMs }}m/s</span>
      <span class="src" :class="weather.source">{{ weather.source === 'LIVE' ? 'LIVE' : '샘플' }}</span>
    </template>
    <span v-else>{{ state === 'failed' ? '날씨 조회 실패' : '날씨 조회 중…' }}</span>
  </div>
</template>

<style scoped>
.pill { display: flex; align-items: center; gap: 8px; background: var(--navy2); border-radius: 18px; padding: 4px 12px; font-size: 12px; white-space: nowrap; }
b { font-size: 14px; }
select { height: 26px; background: var(--navy2); color: #fff; border: 1px solid #3b5a8c; border-radius: 5px; padding: 0 2px 0 6px; }
.src { font-size: 10px; border-radius: 8px; padding: 0 6px; background: #f59e0b; color: #3b2600; }
.src.LIVE { background: #22c55e; color: #052e16; }
@media (max-width: 720px) { .sub { display: none; } }
</style>
