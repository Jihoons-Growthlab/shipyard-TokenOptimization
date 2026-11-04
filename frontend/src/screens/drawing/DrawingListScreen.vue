<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import CodeSelect from '../../components/CodeSelect.vue'
import ScreenHead from '../../components/ScreenHead.vue'
import { useLatest } from '../../composables/useLatest'
import { codeName } from '../../stores/session'
import { toastError } from '../../stores/toast'
import { screenProps } from '../props'
import DrawingDetailModal from './DrawingDetailModal.vue'
import DrawingNewModal from './DrawingNewModal.vue'

const props = defineProps(screenProps)

const blank = () => ({ hull_no: props.param ?? '', discipline: '', status: '', q: '' })
const filters = ref(blank())
const hulls = ref([])
const drawings = ref([])
const selected = ref(null)
const detailId = ref(null)
const creating = ref(false)
const latest = useLatest()

async function load() {
  const seq = latest.next()
  try {
    const result = await api.get('/drawings', { query: filters.value })
    if (latest.isCurrent(seq)) drawings.value = result
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

function reset() {
  filters.value = { hull_no: '', discipline: '', status: '', q: '' }
  load()
}

function open(item) {
  selected.value = item.drawing_id
  detailId.value = item.drawing_id
}

function created(id) {
  creating.value = false
  detailId.value = id
  load()
}

watch(() => props.tick, () => {
  if (props.param) filters.value.hull_no = props.param
  load()
})

onMounted(async () => {
  load()
  try {
    hulls.value = await api.get('/hulls')
  } catch (error) {
    toastError(error)
  }
})
</script>

<template>
  <ScreenHead :title="title" desc="행 더블클릭 또는 [상세]로 도면 상세·PDF 뷰어·리비전·결재 팝업을 엽니다. Rev는 현재 배포(유효) 리비전입니다." :readonly="!canWrite" />
  <form class="filters" @submit.prevent="load">
    <select v-model="filters.hull_no" class="input hull" aria-label="호선">
      <option value="">호선 전체</option>
      <option v-for="hull in hulls" :key="hull.hull_no" :value="hull.hull_no">{{ hull.hull_no }} {{ hull.hull_nm }}</option>
    </select>
    <CodeSelect v-model="filters.discipline" class="input" group="DWGDISC" empty="분야 전체" />
    <CodeSelect v-model="filters.status" class="input" group="DWGSTAT" empty="상태 전체" />
    <input v-model="filters.q" class="input" placeholder="도면번호/도면명" />
    <button class="btn pri">조회</button>
    <button class="btn" type="button" @click="reset">초기화</button>
    <button v-if="canWrite" class="btn pri right" type="button" @click="creating = true">+ 도면 등록</button>
  </form>
  <div class="tw">
    <table class="t">
      <thead>
        <tr>
          <th>도면번호</th><th>도면명</th><th>호선</th><th>블록</th><th>분야</th><th>Rev</th><th>상태</th><th>설계자</th><th>연계공정</th><th />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in drawings" :key="item.drawing_id" class="click" :class="{ selected: selected === item.drawing_id }"
          @click="selected = item.drawing_id" @dblclick="open(item)"
        >
          <td><b class="no">{{ item.drawing_no }}</b></td>
          <td>{{ item.drawing_nm }}</td>
          <td>{{ item.hull_no }}</td>
          <td>{{ item.block_cd }}</td>
          <td>{{ codeName('DWGDISC', item.discipline) }}</td>
          <td>Rev{{ item.current_rev_no }}<span v-if="item.latest_rev_no !== item.current_rev_no" class="muted"> (최신 Rev{{ item.latest_rev_no }})</span></td>
          <td><span class="bdg" :class="item.dwg_status">{{ codeName('DWGSTAT', item.dwg_status) }}</span></td>
          <td>{{ item.designer_nm }}</td>
          <td class="num">{{ item.link_count || '-' }}</td>
          <td class="act"><button class="btn sm" @click.stop="open(item)">상세</button></td>
        </tr>
        <tr v-if="!drawings.length"><td colspan="10" class="empty">조회된 도면이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="total">총 {{ drawings.length }}건</div>
  <DrawingNewModal v-if="creating" :hull-no="filters.hull_no" @created="created" @close="creating = false" />
  <DrawingDetailModal v-if="detailId" :drawing-id="detailId" @changed="load" @close="detailId = null" />
</template>

<style scoped>
.filters select.hull { width: 166px; }
.no { font-size: 13.5px; }
.t td { height: 37px; padding-top: 0; padding-bottom: 0; }
.act { width: 84px; }
</style>
