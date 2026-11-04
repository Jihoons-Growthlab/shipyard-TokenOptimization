<script setup>
import { computed, ref } from 'vue'
import ModalBox from '../../components/ModalBox.vue'
import { codeName } from '../../stores/session'
import HullBlocksTab from './HullBlocksTab.vue'
import HullInfoTab from './HullInfoTab.vue'
import HullMilestonesTab from './HullMilestonesTab.vue'
import HullSummaryTab from './HullSummaryTab.vue'
import HullViewerTab from './HullViewerTab.vue'

const props = defineProps({ hullNo: { type: String, default: null }, canWrite: Boolean })
const emit = defineEmits(['changed', 'close'])

const DATA_TABS = [
  { id: 'info', label: '기본정보', component: HullInfoTab },
  { id: 'milestones', label: '주요일정', component: HullMilestonesTab },
  { id: 'blocks', label: '블록 구성', component: HullBlocksTab },
  { id: 'summary', label: '연계 현황', component: HullSummaryTab },
]

const VIEWER_TAB = '3d'

const current = ref(props.hullNo)
const tab = ref('info')
const dataTab = ref('info')
const reloadKey = ref(0)
const hull = ref(null)

const dataComponent = computed(() => DATA_TABS.find((item) => item.id === dataTab.value).component)
const subtitle = computed(() => {
  if (!current.value) return '신규 호선을 등록합니다.'
  return hull.value ? codeName('HULLSTAT', hull.value.hull_status) : ''
})

function select(id) {
  if (id === tab.value) return
  const backFromViewer = tab.value === VIEWER_TAB && id === dataTab.value
  tab.value = id
  if (id === VIEWER_TAB || backFromViewer) return
  dataTab.value = id
  reloadKey.value += 1
}

function created(result) {
  hull.value = result
  current.value = result.hull_no
  reloadKey.value += 1
  emit('changed')
}
</script>

<template>
  <ModalBox :title="current ? `호선 ${current}` : '호선 등록'" :size="tab === VIEWER_TAB ? 'xl' : 'large'" @close="emit('close')">
    <p class="subtitle">{{ subtitle }}</p>
    <div v-if="current" class="subtabs">
      <button
        v-for="item in DATA_TABS" :key="item.id" :class="{ active: tab === item.id }" @click="select(item.id)"
      >{{ item.label }}</button>
      <button :class="{ active: tab === VIEWER_TAB }" @click="select(VIEWER_TAB)">3D 보기</button>
    </div>
    <HullViewerTab v-if="tab === VIEWER_TAB" />
    <component
      :is="dataComponent" v-show="tab !== VIEWER_TAB" :key="`${dataTab}:${current}:${reloadKey}`" :hull-no="current" :can-write="canWrite"
      @loaded="hull = $event" @created="created" @changed="emit('changed')" @deleted="emit('changed'); emit('close')"
    />
  </ModalBox>
</template>

<style scoped>
.subtitle { font-size: 12px; color: var(--muted); margin-bottom: 10px; min-height: 15px; }
</style>
