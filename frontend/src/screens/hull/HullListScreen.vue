<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import CodeSelect from '../../components/CodeSelect.vue'
import ProgressBar from '../../components/ProgressBar.vue'
import ScreenHead from '../../components/ScreenHead.vue'
import { useLatest } from '../../composables/useLatest'
import { screenProps } from '../props'
import { codeName } from '../../stores/session'
import { toastError } from '../../stores/toast'
import HullModal from './HullModal.vue'

const props = defineProps(screenProps)

const blank = () => ({ status: '', ship_type: '', q: '' })
const filters = ref(blank())
const hulls = ref([])
const selected = ref(null)
const modal = ref(null)
const latest = useLatest()

async function load() {
  const seq = latest.next()
  try {
    const result = await api.get('/hulls', { query: filters.value })
    if (latest.isCurrent(seq)) hulls.value = result
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

function reset() {
  filters.value = blank()
  load()
}

function open(hullNo) {
  selected.value = hullNo
  modal.value = { hullNo }
}

onMounted(load)
watch(() => props.tick, load)
</script>

<template>
  <ScreenHead :title="title" desc="행을 더블클릭하거나 [상세]를 누르면 호선 상세 팝업이 열립니다." :readonly="!canWrite" />
  <form class="filters" @submit.prevent="load">
    <CodeSelect v-model="filters.status" class="input" group="HULLSTAT" empty="상태 전체" />
    <CodeSelect v-model="filters.ship_type" class="input" group="SHIPTYPE" empty="선종 전체" />
    <input v-model="filters.q" class="input" placeholder="호선번호/호선명/선주" />
    <button class="btn pri">조회</button>
    <button class="btn" type="button" @click="reset">초기화</button>
    <button v-if="canWrite" class="btn pri right" type="button" @click="modal = { hullNo: null }">+ 호선 등록</button>
  </form>
  <div class="tw">
    <table class="t">
      <thead>
        <tr>
          <th>호선번호</th><th>호선명</th><th>선종</th><th>상태</th><th>선주</th><th>선급</th><th>도크</th>
          <th>계약일</th><th>인도예정</th><th>진척률</th><th>지연</th><th />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="hull in hulls" :key="hull.hull_no" class="click" :class="{ selected: selected === hull.hull_no }"
          @click="selected = hull.hull_no" @dblclick="open(hull.hull_no)"
        >
          <td><b class="no">{{ hull.hull_no }}</b></td>
          <td>{{ hull.hull_nm }}</td>
          <td>{{ codeName('SHIPTYPE', hull.ship_type) }}</td>
          <td><span class="bdg info">{{ codeName('HULLSTAT', hull.hull_status) }}</span></td>
          <td>{{ hull.owner_nm }}</td>
          <td>{{ hull.class_society }}</td>
          <td>{{ hull.dock_no || '-' }}</td>
          <td>{{ hull.contract_dt }}</td>
          <td>{{ hull.delivery_dt }}</td>
          <td class="prog">
            <ProgressBar v-if="hull.progress !== null" :value="hull.progress" />
            <span v-else class="muted">계획 없음</span>
          </td>
          <td class="num">{{ hull.delay_count || '-' }}</td>
          <td class="act"><button class="btn sm" @click.stop="open(hull.hull_no)">상세</button></td>
        </tr>
        <tr v-if="!hulls.length"><td colspan="12" class="empty">조회된 호선이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
  <div class="total">총 {{ hulls.length }}척</div>
  <HullModal
    v-if="modal" :hull-no="modal.hullNo" :can-write="canWrite"
    @changed="load" @close="modal = null"
  />
</template>

<style scoped>
.no { font-size: 13.5px; }
.t td { height: 37px; padding-top: 0; padding-bottom: 0; }
.prog { width: 150px; }
.act { width: 88px; }
.btn.sm { height: 24px; padding: 0 8px; }
</style>
