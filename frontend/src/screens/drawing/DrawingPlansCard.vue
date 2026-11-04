<script setup>
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import { codeName } from '../../stores/session'
import { navigate } from '../../stores/shell'
import { toast, toastError, toastOk } from '../../stores/toast'

const props = defineProps({ drawing: { type: Object, required: true }, canWrite: Boolean })
const emit = defineEmits(['changed'])

const planId = ref('')
const required = ref(true)
const url = computed(() => `/drawings/${props.drawing.drawing_id}/plans`)
const impact = computed(() => {
  const items = props.drawing.impacts
  if (!items.length) return ''
  const labels = items.map((item) => item.plan_label).join(', ')
  return `⚠ 최근 개정(Rev${items[0].rev_no}, ${items[0].issue_dt})으로 이미 착수·완료된 공정 ${items.length}건이 영향을 받습니다: ${labels}`
})

async function add() {
  if (!planId.value) {
    toast('공정을 선택하세요.', 'error')
    return
  }
  try {
    await api.post(url.value, { plan_id: Number(planId.value), required: required.value })
    planId.value = ''
    toastOk('공정이 연계되었습니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

async function remove(plan) {
  try {
    await api.del(`${url.value}/${plan.plan_id}`)
    toastOk('연계가 해제되었습니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}
</script>

<template>
  <section class="card">
    <h3>연계 공정 <span class="bdg">{{ drawing.plans.length }}</span></h3>
    <div v-if="impact" class="note warn">{{ impact }}</div>
    <div class="tw">
      <table class="t">
        <thead><tr><th>공정</th><th>상태</th><th>필수</th><th>필요일</th><th v-if="canWrite" /></tr></thead>
        <tbody>
          <tr v-for="plan in drawing.plans" :key="plan.plan_id">
            <td><button class="lnk" @click="navigate('plan-gantt', drawing.hull_no)">{{ plan.label }}</button></td>
            <td><span class="bdg" :class="plan.plan_status">{{ codeName('PLANSTAT', plan.plan_status) }}</span></td>
            <td>{{ plan.required ? '필수' : '참고' }}</td>
            <td>{{ plan.need_dt }}</td>
            <td v-if="canWrite"><button class="btn sm danger" @click="remove(plan)">해제</button></td>
          </tr>
          <tr v-if="!drawing.plans.length"><td :colspan="canWrite ? 5 : 4" class="empty">연계된 공정이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div v-if="canWrite" class="add">
      <select v-model="planId" class="input" aria-label="공정 선택">
        <option value="">공정 선택</option>
        <option v-for="plan in drawing.available_plans" :key="plan.plan_id" :value="plan.plan_id">{{ plan.label }}</option>
      </select>
      <label class="check"><input v-model="required" type="checkbox" />필수</label>
      <button class="btn" @click="add">+ 공정 연계</button>
    </div>
  </section>
</template>

<style scoped>
.lnk { background: none; border: 0; padding: 0; color: var(--pri-d); cursor: pointer; }
.add { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.add .input { flex: 1; min-width: 0; }
.note { margin-bottom: 8px; }
</style>
