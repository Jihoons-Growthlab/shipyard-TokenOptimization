<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ganttLayout, HEAD_H, initialScroll, LEFT_W } from '../../lib/gantt'
import { codeName } from '../../stores/session'

const props = defineProps({
  plans: { type: Array, required: true },
  deps: { type: Array, required: true },
  today: { type: String, required: true },
  zoom: { type: Number, required: true },
  selectedId: { type: Number, default: null },
  scrollKey: { type: String, default: '' },
})
const emit = defineEmits(['select'])

const scroller = ref(null)
const layout = computed(() => ganttLayout(props.plans, props.deps, props.today, props.zoom))
let pendingScroll = true
let observer

function applyInitialScroll() {
  const element = scroller.value
  if (!pendingScroll || !element || !element.clientWidth || !props.plans.length) return
  pendingScroll = false
  element.scrollLeft = initialScroll(layout.value.todayX, element.clientWidth)
}

watch(() => props.scrollKey, () => {
  pendingScroll = true
  if (scroller.value) scroller.value.scrollTop = 0
})
watch(() => [props.plans, props.scrollKey], () => nextTick(applyInitialScroll))

onMounted(() => {
  applyInitialScroll()
  observer = new ResizeObserver(applyInitialScroll)
  observer.observe(scroller.value)
})
onBeforeUnmount(() => observer?.disconnect())

function barTitle(plan) {
  const parts = [plan.label, `${plan.plan_start_dt} ~ ${plan.plan_end_dt}`, `진척 ${plan.progress_rate}%`, codeName('PLANSTAT', plan.plan_status)]
  if (plan.drawing_wait) parts.push('도면 대기')
  return parts.join(' | ')
}

const rowName = (plan) => plan.block_cd ?? '호선'
</script>

<template>
  <div ref="scroller" class="gantt">
    <div v-if="!plans.length" class="none">표시할 공정이 없습니다.</div>
    <div v-else class="sheet" :style="{ width: `${layout.width}px`, height: `${layout.height}px` }">
      <div class="head" :style="{ height: `${HEAD_H}px` }">
        <div class="corner" :style="{ width: `${LEFT_W}px` }">블록 / 공정</div>
        <div class="months">
          <span v-for="month in layout.months" :key="month.key" :style="{ left: `${month.x}px` }">{{ month.label }}</span>
        </div>
      </div>
      <div class="rows">
        <div
          v-for="plan in plans" :key="plan.plan_id" class="row" :class="{ selected: plan.plan_id === selectedId }"
        >
          <button class="name" :style="{ width: `${LEFT_W}px` }" @click="emit('select', plan)">
            <span class="code">{{ rowName(plan) }}</span>{{ plan.proc_nm }}<span v-if="plan.blockers.length"> 📐</span>
          </button>
        </div>
        <div class="chart" :style="{ left: `${LEFT_W}px`, width: `${layout.chartWidth}px` }">
          <svg class="links" :width="layout.chartWidth" :height="layout.height - HEAD_H">
            <path v-for="link in layout.links" :key="link.key" :d="link.d" />
          </svg>
          <button
            v-for="bar in layout.bars" :key="bar.plan.plan_id" class="bar" :class="bar.plan.plan_status"
            :title="barTitle(bar.plan)" :style="{ left: `${bar.x}px`, top: `${bar.top}px`, width: `${bar.width}px` }"
            @click="emit('select', bar.plan)"
          ><i :style="{ width: `${bar.plan.progress_rate}%` }" /></button>
          <div v-for="month in layout.months" :key="month.key" class="month-line" :style="{ left: `${month.x}px` }" />
          <div class="today" :style="{ left: `${layout.todayX}px` }"><span>오늘</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gantt { flex: 1; min-height: 140px; overflow: auto; background: #fff; border: 1px solid var(--line); border-radius: 6px; margin-bottom: 10px; position: relative; }
.none { padding: 24px; text-align: center; color: var(--muted); }
.sheet { position: relative; }
.head { position: sticky; top: 0; z-index: 4; display: flex; background: var(--head); border-bottom: 1px solid var(--line); }
.corner { position: sticky; left: 0; z-index: 5; background: var(--head); padding: 0 9px; display: flex; align-items: center; font-weight: 600; flex: none; font-size: 12px; }
.months { position: relative; flex: 1; }
.months span { position: absolute; top: 3px; padding-left: 5px; font-size: 11px; color: var(--muted); border-left: 1px solid var(--line); height: 30px; white-space: nowrap; }
.rows { position: relative; }
.row { height: 28px; box-shadow: inset 0 -1px var(--line2); }
.row.selected, .row.selected .name { background: var(--sel); }
.name { position: sticky; left: 0; z-index: 3; display: flex; align-items: center; height: 28px; padding: 0 9px; background: #fff; border: 0; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line2); cursor: pointer; text-align: left; white-space: pre; font-size: 12px; }
.name:hover { background: var(--hover); }
.code { color: var(--muted); width: 33px; flex: none; }
.chart { position: absolute; top: 0; bottom: 0; z-index: 1; pointer-events: none; }
.links { position: absolute; inset: 0; }
.links path { fill: none; stroke: #64748b; stroke-width: 1; opacity: .55; }
.bar {
  --c: var(--c-PLAN);
  position: absolute; height: 16px; border-radius: 3px; padding: 0; overflow: hidden; pointer-events: auto; cursor: pointer;
  background: color-mix(in srgb, var(--c) 35%, #fff); border: 1px solid color-mix(in srgb, var(--c) 60%, #fff);
}
.bar.READY { --c: var(--c-READY); } .bar.WORK { --c: var(--c-WORK); } .bar.DONE { --c: var(--c-DONE); } .bar.DELAY { --c: var(--c-DELAY); }
.bar i { display: block; height: 100%; background: var(--c); }
.month-line { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--line); }
.today { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--err); }
.today span { position: absolute; left: 4px; top: 2px; font-size: 10px; color: var(--err); background: #fff; padding: 0 2px; white-space: nowrap; }
</style>
