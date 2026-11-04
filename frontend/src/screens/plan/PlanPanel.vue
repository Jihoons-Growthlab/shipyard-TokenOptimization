<script setup>
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import { addDays } from '../../lib/dates'
import { codeName } from '../../stores/session'
import { toastError, toastOk } from '../../stores/toast'
import PlanLinks from './PlanLinks.vue'

const props = defineProps({
  plan: { type: Object, default: null },
  hullNo: { type: String, required: true },
  today: { type: String, required: true },
  defaultBlock: { type: [Number, String], default: '' },
  blocks: { type: Array, required: true },
  procs: { type: Array, required: true },
  users: { type: Array, required: true },
  allPlans: { type: Array, required: true },
  canWrite: Boolean,
})
const emit = defineEmits(['saved', 'deleted', 'close', 'links-changed', 'open-drawing'])

function initial() {
  const plan = props.plan
  if (!plan) {
    return {
      block_id: props.defaultBlock, proc_cd: 'CUT', plan_start_dt: props.today, plan_end_dt: addDays(props.today, 13),
      manager_emp_no: '', pred_plan_ids: [], remark: '',
    }
  }
  return {
    block_id: plan.block_id ?? '', proc_cd: plan.proc_cd, plan_start_dt: plan.plan_start_dt, plan_end_dt: plan.plan_end_dt,
    manager_emp_no: plan.manager_emp_no ?? '', pred_plan_ids: [...plan.pred_plan_ids], remark: plan.remark ?? '',
  }
}

const form = ref(initial())
const predOptions = computed(() => props.allPlans.filter((item) => item.plan_id !== props.plan?.plan_id))
const links = ref(null)
const sub = computed(() => {
  const plan = props.plan
  return `진척 ${plan.progress_rate}% · 실제 ${plan.actual_start_dt ?? '-'} ~ ${plan.actual_end_dt ?? '-'}`
})

async function send(confirmLate) {
  const body = { ...form.value, block_id: form.value.block_id || null, confirm_late_preds: confirmLate }
  return props.plan ? api.patch(`/plans/${props.plan.plan_id}`, body) : api.post(`/hulls/${props.hullNo}/plans`, body)
}

async function save() {
  try {
    let saved
    try {
      saved = await send(false)
    } catch (error) {
      if (error.code !== 'PRED_LATE_CONFIRM_REQUIRED') throw error
      if (!window.confirm(error.message)) return
      saved = await send(true)
    }
    toastOk('저장되었습니다.')
    emit('saved', saved)
  } catch (error) {
    toastError(error)
  }
}

async function remove() {
  if (!window.confirm('공정을 삭제합니다. (실적·선후행·도면 연계 함께 삭제)')) return
  try {
    await api.del(`/plans/${props.plan.plan_id}`)
    toastOk('삭제되었습니다.')
    emit('deleted')
  } catch (error) {
    toastError(error)
  }
}
</script>

<template>
  <section class="card panel">
    <h3 class="head">
      <template v-if="plan">
        {{ plan.label }} <span class="bdg" :class="plan.plan_status">{{ codeName('PLANSTAT', plan.plan_status) }}</span>
        <span class="info">{{ sub }}</span>
      </template>
      <template v-else>공정 추가</template>
    </h3>
    <div class="grid">
      <form class="form" @submit.prevent="save">
        <div class="field block"><label>블록</label>
          <select v-model="form.block_id" :disabled="!canWrite">
            <option value="">호선 전체(블록 없음)</option>
            <option v-for="block in blocks" :key="block.block_id" :value="block.block_id">{{ block.block_cd }} {{ block.block_nm }}</option>
          </select>
        </div>
        <div class="field proc"><label>공정</label>
          <select v-model="form.proc_cd" :disabled="!canWrite">
            <option v-for="proc in procs" :key="proc.proc_cd" :value="proc.proc_cd">{{ proc.proc_nm }}</option>
          </select>
        </div>
        <div class="field"><label>계획 시작</label><input v-model="form.plan_start_dt" type="date" :disabled="!canWrite" /></div>
        <div class="field"><label>계획 종료</label><input v-model="form.plan_end_dt" type="date" :disabled="!canWrite" /></div>
        <div class="field mgr"><label>담당자</label>
          <select v-model="form.manager_emp_no" :disabled="!canWrite">
            <option value="">미지정</option>
            <option v-for="user in users" :key="user.emp_no" :value="user.emp_no">{{ user.display_name }} ({{ user.emp_no }})</option>
          </select>
        </div>
        <div class="field half"><label>선행 공정 (Ctrl 다중선택)</label>
          <select v-model="form.pred_plan_ids" multiple class="multi" :disabled="!canWrite">
            <option v-for="item in predOptions" :key="item.plan_id" :value="item.plan_id">{{ item.label }}</option>
          </select>
        </div>
        <div class="field half"><label>비고</label><textarea v-model="form.remark" class="multi" maxlength="1000" :disabled="!canWrite" /></div>
        <div class="buttons">
          <button class="btn pri" :disabled="!canWrite">저장</button>
          <button v-if="plan" class="btn danger" type="button" :disabled="!canWrite" @click="remove">삭제</button>
          <button class="btn" type="button" @click="emit('close')">닫기</button>
        </div>
      </form>
      <PlanLinks
        v-if="plan" ref="links" :key="plan.plan_id" :plan-id="plan.plan_id" :can-write="canWrite"
        @changed="emit('links-changed')" @open-drawing="emit('open-drawing', $event)"
      />
      <p v-else class="muted hint">저장한 뒤 이 공정에 도면을 연계할 수 있습니다.</p>
    </div>
  </section>
</template>

<style scoped>
.panel { margin: 0; flex: none; }
.card > h3.head { justify-content: flex-start; gap: 7px; margin-bottom: 8px; }
.info { font-weight: 400; font-size: 13px; color: var(--muted); }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 430px; gap: 16px; }
.form { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px 12px; align-items: end; }
.block { grid-column: span 2; }
.half { grid-column: span 3; }
.field .multi { height: 66px; padding: 2px 8px; }
.buttons { grid-column: 1 / -1; display: flex; gap: 8px; }
.hint { padding-top: 6px; font-size: 12.5px; }
@media (max-width: 1560px) {
  .form { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .block, .proc, .mgr, .half { grid-column: span 2; }
}
</style>
