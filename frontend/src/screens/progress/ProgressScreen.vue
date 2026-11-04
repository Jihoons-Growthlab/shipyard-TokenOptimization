<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import ProgressBar from '../../components/ProgressBar.vue'
import ScreenHead from '../../components/ScreenHead.vue'
import { useLatest } from '../../composables/useLatest'
import { codeName, session } from '../../stores/session'
import { toastError, toastOk } from '../../stores/toast'
import { screenProps } from '../props'

defineProps(screenProps)

const hulls = ref([])
const hullNo = ref('')
const includeDone = ref(false)
const plans = ref([])
const selectedId = ref(null)
const detail = ref(null)
const users = ref([])
const form = ref({})
const listLatest = useLatest()
const detailLatest = useLatest()

const today = computed(() => session.user?.today ?? '')

function resetForm(rate = 0) {
  form.value = {
    work_dt: today.value, progress_rate: rate, man_hour: '', worker_cnt: '', worker_emp_no: session.user?.emp_no ?? '', remark: '',
  }
}

async function loadPlans() {
  const seq = listLatest.next()
  try {
    const result = await api.get(`/hulls/${hullNo.value}/progress-targets`, { query: { include_done: includeDone.value } })
    if (listLatest.isCurrent(seq)) plans.value = result.plans
  } catch (error) {
    if (listLatest.isCurrent(seq)) toastError(error)
  }
}

function clearSelection() {
  detailLatest.next()
  selectedId.value = null
  detail.value = null
}

function changeHull() {
  clearSelection()
  loadPlans()
}

function applyDetail(result) {
  detail.value = result
  resetForm(result.plan.progress_rate)
}

async function select(plan) {
  selectedId.value = plan.plan_id
  const seq = detailLatest.next()
  try {
    const result = await api.get(`/plans/${plan.plan_id}/progress`)
    if (detailLatest.isCurrent(seq)) applyDetail(result)
  } catch (error) {
    if (detailLatest.isCurrent(seq)) toastError(error)
  }
}

const toNumber = (value) => (value === '' || value === null ? null : Number(value))

async function save() {
  const { work_dt: workDt, progress_rate: rate, man_hour: hours, worker_cnt: count, worker_emp_no: worker, remark } = form.value
  try {
    const result = await api.put(`/plans/${selectedId.value}/progress/${workDt || '-'}`, {
      progress_rate: toNumber(rate), man_hour: toNumber(hours), worker_cnt: toNumber(count), worker_emp_no: worker, remark,
    })
    applyDetail(result)
    toastOk(result.plan.progress_rate >= 100 ? '실적 저장 — 공정이 완료 처리되었습니다.' : '실적이 저장되었습니다.')
    await loadPlans()
  } catch (error) {
    toastError(error)
  }
}

async function remove(item) {
  if (!window.confirm('실적을 삭제합니다.')) return
  try {
    applyDetail(await api.del(`/progress/${item.progress_id}`))
    toastOk('실적이 삭제되었습니다.')
    await loadPlans()
  } catch (error) {
    toastError(error)
  }
}

onMounted(async () => {
  try {
    const [result, options] = await Promise.all([api.get('/progress-hulls'), api.get('/users/options')])
    hulls.value = result.hulls
    users.value = options
    hullNo.value = result.default_hull_no ?? result.hulls[0]?.hull_no ?? ''
    if (hullNo.value) await loadPlans()
  } catch (error) {
    toastError(error)
  }
})
</script>

<template>
  <ScreenHead title="공정 실적 입력" desc="착수 가능/진행/지연 공정의 일별 진척률·공수를 입력하면 공정 진척과 상태가 갱신됩니다." :readonly="!canWrite" />
  <div class="tools">
    <select v-model="hullNo" class="input" aria-label="호선" @change="changeHull">
      <option v-for="hull in hulls" :key="hull.hull_no" :value="hull.hull_no">{{ hull.hull_no }} {{ hull.hull_nm }}</option>
    </select>
    <label class="check"><input v-model="includeDone" type="checkbox" @change="loadPlans" />완료 공정 포함</label>
  </div>
  <div class="tw">
    <table class="t">
      <thead><tr><th>공정</th><th>계획기간</th><th>실제착수</th><th>진척</th><th>상태</th><th>담당</th></tr></thead>
      <tbody>
        <tr
          v-for="plan in plans" :key="plan.plan_id" class="click" :class="{ selected: plan.plan_id === selectedId }"
          @click="select(plan)"
        >
          <td>{{ plan.label }}</td>
          <td>{{ plan.plan_start_dt }} ~ {{ plan.plan_end_dt }}</td>
          <td>{{ plan.actual_start_dt }}</td>
          <td class="bar"><ProgressBar :value="plan.progress_rate" /></td>
          <td><span class="bdg" :class="plan.plan_status">{{ codeName('PLANSTAT', plan.plan_status) }}</span></td>
          <td>{{ plan.manager_nm }}</td>
        </tr>
        <tr v-if="!plans.length"><td colspan="6" class="empty">대상 공정이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
  <p v-if="!selectedId" class="muted pick">위 목록에서 공정을 선택하세요.</p>
  <section v-else-if="detail" class="card detail">
    <h3>{{ detail.plan.label }} <span class="bdg" :class="detail.plan.plan_status">{{ codeName('PLANSTAT', detail.plan.plan_status) }}</span></h3>
    <form v-if="canWrite" class="fg c6" @submit.prevent="save">
      <div class="field"><label>작업일</label><input v-model="form.work_dt" type="date" :max="today" /></div>
      <div class="field"><label>누적 진척률(%)</label><input v-model="form.progress_rate" type="number" min="0" max="100" step="1" /></div>
      <div class="field"><label>투입 공수(MH)</label><input v-model="form.man_hour" type="number" step=".5" /></div>
      <div class="field"><label>투입 인원</label><input v-model="form.worker_cnt" type="number" step="1" /></div>
      <div class="field"><label>작업자</label>
        <select v-model="form.worker_emp_no">
          <option value="">-</option>
          <option v-for="user in users" :key="user.emp_no" :value="user.emp_no">{{ user.display_name }} ({{ user.emp_no }})</option>
        </select>
      </div>
      <div><button class="btn pri">실적 저장</button></div>
      <div class="field"><label>비고</label><input v-model="form.remark" maxlength="1000" /></div>
    </form>
    <h3 class="hist">실적 이력</h3>
    <div class="tw">
      <table class="t hist-t">
        <thead>
          <tr><th>작업일</th><th>누적 진척률</th><th>공수</th><th>인원</th><th>작업자</th><th>비고</th><th v-if="canWrite" /></tr>
        </thead>
        <tbody>
          <tr v-for="item in detail.history" :key="item.progress_id">
            <td>{{ item.work_dt }}</td>
            <td>{{ item.progress_rate }}%</td>
            <td class="num">{{ item.man_hour }}</td>
            <td class="num">{{ item.worker_cnt }}</td>
            <td>{{ item.worker_nm }}</td>
            <td class="wrap">{{ item.remark }}</td>
            <td v-if="canWrite"><button class="btn sm danger" @click="remove(item)">삭제</button></td>
          </tr>
          <tr v-if="!detail.history.length"><td :colspan="canWrite ? 7 : 6" class="empty">실적 이력이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.tools { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.tools .input { width: auto; }
.bar { width: 22%; }
.pick { margin-top: 12px; }
.detail { margin-top: 12px; }
.card > h3.hist { margin: 16px 0 10px; }
.hist-t th:nth-child(1) { width: 21%; } .hist-t th:nth-child(2) { width: 20%; } .hist-t th:nth-child(3) { width: 10%; }
.hist-t th:nth-child(4) { width: 10%; } .hist-t th:nth-child(5) { width: 13%; } .hist-t th:nth-child(6) { width: 11%; }
.hist-t td { height: 37px; padding-top: 0; padding-bottom: 0; }
</style>
