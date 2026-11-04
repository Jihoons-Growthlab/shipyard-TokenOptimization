<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import ProgressBar from '../../components/ProgressBar.vue'
import ScreenHead from '../../components/ScreenHead.vue'
import DrawingDetailModal from '../drawing/DrawingDetailModal.vue'
import { useLatest } from '../../composables/useLatest'
import { session } from '../../stores/session'
import { toastError } from '../../stores/toast'
import { screenProps } from '../props'
import GanttChart from './GanttChart.vue'
import PlanPanel from './PlanPanel.vue'

const props = defineProps(screenProps)
const STATUSES = [['PLAN', '계획'], ['READY', '착수가능'], ['WORK', '진행'], ['DONE', '완료'], ['DELAY', '지연']]
const ZOOMS = [[2.5, '축소'], [4, '보통'], [6, '확대']]

const hulls = ref([])
const hullNo = ref('')
const blockId = ref('')
const zoom = ref(4)
const data = ref(null)
const blocks = ref([])
const procs = ref([])
const users = ref([])
const selectedId = ref(null)
const creating = ref(false)
const scrollKey = ref('')
const drawingId = ref(null)
const latest = useLatest()
let hullChange = 0

const today = computed(() => data.value?.today ?? session.user?.today ?? '')
const plans = computed(() => {
  const all = data.value?.plans ?? []
  return blockId.value ? all.filter((plan) => plan.block_id === blockId.value) : all
})
const selected = computed(() => data.value?.plans.find((plan) => plan.plan_id === selectedId.value) ?? null)
const panelOpen = computed(() => creating.value || selected.value)

async function reload() {
  const seq = latest.next()
  const target = hullNo.value
  try {
    const result = await api.get(`/hulls/${target}/plans`)
    if (latest.isCurrent(seq)) data.value = result
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

async function selectHull(next) {
  const change = ++hullChange
  hullNo.value = next
  blockId.value = ''
  selectedId.value = null
  creating.value = false
  if (!next) return
  await Promise.all([
    reload(),
    api.get(`/hulls/${next}/blocks`).then((result) => { if (change === hullChange) blocks.value = result }).catch(toastError),
  ])
  if (change === hullChange) scrollKey.value = `${next}:${change}`
}

const defaultHull = () =>
  (props.param && hulls.value.find((hull) => hull.hull_no === props.param)?.hull_no)
  ?? (hulls.value.find((hull) => hull.plan_count > 0) ?? hulls.value[0])?.hull_no ?? ''

onMounted(async () => {
  try {
    const [hullList, procList, userList] = await Promise.all([api.get('/plan-hulls'), api.get('/procs'), api.get('/users/options')])
    hulls.value = hullList
    procs.value = procList
    users.value = userList
    await selectHull(defaultHull())
  } catch (error) {
    toastError(error)
  }
})

watch(() => props.tick, () => {
  if (props.param && props.param !== hullNo.value) selectHull(defaultHull())
})

function select(plan) {
  creating.value = false
  selectedId.value = plan.plan_id
}

function add() {
  selectedId.value = null
  creating.value = true
}

function close() {
  selectedId.value = null
  creating.value = false
}

async function saved(plan) {
  await reload()
  select(plan)
}

async function deleted() {
  close()
  await reload()
}

</script>

<template>
  <div class="screen">
    <ScreenHead :title="title" desc="막대 또는 좌측 공정명을 클릭하면 아래에 상세·수정 패널이 열립니다." :readonly="!canWrite" />
    <div class="tools">
      <select class="input" :value="hullNo" aria-label="호선" @change="selectHull($event.target.value)">
        <option v-for="hull in hulls" :key="hull.hull_no" :value="hull.hull_no">{{ hull.hull_no }} {{ hull.hull_nm }}</option>
      </select>
      <select v-model="blockId" class="input" aria-label="블록">
        <option value="">블록 전체</option>
        <option v-for="block in blocks" :key="block.block_id" :value="block.block_id">{{ block.block_cd }} {{ block.block_nm }}</option>
      </select>
      <select v-model.number="zoom" class="input zoom" aria-label="배율">
        <option v-for="[value, label] in ZOOMS" :key="value" :value="value">{{ label }}</option>
      </select>
      <span>호선 진척</span>
      <ProgressBar class="hp" :value="data?.hull_progress ?? 0" />
      <button v-if="canWrite" class="btn pri right" @click="add">+ 공정 추가</button>
    </div>
    <div class="legend">
      <span v-for="[code, label] in STATUSES" :key="code"><i :style="{ background: `var(--c-${code})` }" />{{ label }}</span>
      <span>📐 도면 대기</span>
      <span class="muted">— 선후행 연결선 / 빨간선 = 오늘({{ today }})</span>
    </div>
    <GanttChart
      v-if="data" :plans="plans" :deps="data.deps" :today="data.today" :zoom="zoom" :selected-id="selectedId"
      :scroll-key="scrollKey" @select="select"
    />
    <PlanPanel
      v-if="panelOpen && data" :key="selectedId ?? 'new'" :plan="selected" :hull-no="hullNo" :today="today"
      :default-block="blockId" :blocks="blocks" :procs="procs" :users="users" :all-plans="data.plans" :can-write="canWrite"
      @saved="saved" @deleted="deleted" @close="close" @links-changed="reload" @open-drawing="drawingId = $event"
    />
    <DrawingDetailModal v-if="drawingId" :drawing-id="drawingId" @changed="reload" @close="drawingId = null" />
  </div>
</template>

<style scoped>
.screen { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.tools { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
.tools .input { width: auto; }
.tools .zoom { width: 110px; }
.hp { width: 170px; }
.right { margin-left: auto; }
.legend { display: flex; align-items: center; gap: 14px; font-size: 12px; margin-bottom: 9px; }
.legend span { display: inline-flex; align-items: center; gap: 4px; }
.legend i { width: 12px; height: 10px; border-radius: 2px; }
</style>
