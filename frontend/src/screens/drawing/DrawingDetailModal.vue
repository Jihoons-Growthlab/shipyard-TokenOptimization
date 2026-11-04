<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import ModalBox from '../../components/ModalBox.vue'
import { useLatest } from '../../composables/useLatest'
import { codeName } from '../../stores/session'
import { canWrite as menuWrite } from '../../stores/shell'
import { toastError, toastOk } from '../../stores/toast'
import DrawingForm from './DrawingForm.vue'
import DrawingPlansCard from './DrawingPlansCard.vue'
import DrawingViewer from './DrawingViewer.vue'
import RevisionCard from './RevisionCard.vue'
import { RESULT_BADGES, STEP_NAMES } from './drawingApi'

const props = defineProps({ drawingId: { type: Number, required: true } })
const emit = defineEmits(['changed', 'close'])

const drawing = ref(null)
const revNo = ref(0)
const form = reactive({ drawing_no: '', drawing_nm: '', discipline: '', hull_no: '', block_id: '', designer_emp_no: '' })
const latest = useLatest()
const canWrite = computed(() => menuWrite('dwg-list'))

function applyForm(item) {
  Object.assign(form, {
    drawing_no: item.drawing_no, drawing_nm: item.drawing_nm, discipline: item.discipline ?? '', hull_no: item.hull_no,
    block_id: item.block_id ?? '', designer_emp_no: item.designer_emp_no ?? '',
  })
}

async function load() {
  const seq = latest.next()
  try {
    const result = await api.get(`/drawings/${props.drawingId}`)
    if (!latest.isCurrent(seq)) return
    if (!drawing.value) revNo.value = result.revisions[0].rev_no
    drawing.value = result
    applyForm(result)
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

async function changed() {
  await load()
  emit('changed')
}

async function save() {
  try {
    const { drawing_nm, discipline, block_id, designer_emp_no } = form
    await api.patch(`/drawings/${props.drawingId}`, { drawing_nm, discipline, block_id: block_id || null, designer_emp_no })
    toastOk('저장되었습니다.')
    await changed()
  } catch (error) {
    toastError(error)
  }
}

async function remove() {
  if (!window.confirm('도면과 리비전·결재·공정 연계를 삭제합니다.')) return
  try {
    await api.del(`/drawings/${props.drawingId}`)
    toastOk('삭제되었습니다.')
    emit('changed')
    emit('close')
  } catch (error) {
    toastError(error)
  }
}

onMounted(load)
</script>

<template>
  <ModalBox :title="drawing ? `도면 ${drawing.drawing_no}` : '도면'" size="xl" @close="emit('close')">
    <div v-if="drawing" class="layout">
      <DrawingViewer v-model:rev-no="revNo" :drawing="drawing" :can-write="canWrite" @changed="changed" />
      <div class="side">
        <p class="meta">{{ drawing.hull_no }} · {{ codeName('DWGDISC', drawing.discipline) }} · {{ drawing.drawing_nm }}</p>
        <form class="card" @submit.prevent="save">
          <h3>도면 정보</h3>
          <DrawingForm :form="form" :disabled="!canWrite" />
          <div v-if="canWrite" class="buttons">
            <button class="btn pri">저장</button>
            <button class="btn danger" type="button" @click="remove">삭제</button>
          </div>
        </form>
        <RevisionCard v-model:rev-no="revNo" :drawing="drawing" :can-write="canWrite" @changed="changed" />
        <section class="card">
          <h3>결재 이력</h3>
          <div class="tw">
            <table class="t">
              <thead><tr><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th></tr></thead>
              <tbody>
                <tr v-for="item in drawing.approvals" :key="item.approval_id" :title="`${item.comment ?? ''} ${item.act_dt ?? ''}`.trim()">
                  <td>Rev{{ item.rev_no }}</td>
                  <td>{{ STEP_NAMES[item.step_no] }}</td>
                  <td>{{ item.approver_nm }}</td>
                  <td><span class="bdg" :class="RESULT_BADGES[item.result][0]">{{ RESULT_BADGES[item.result][1] }}</span></td>
                </tr>
                <tr v-if="!drawing.approvals.length"><td colspan="4" class="empty">결재 이력이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <DrawingPlansCard :drawing="drawing" :can-write="canWrite" @changed="changed" />
      </div>
    </div>
  </ModalBox>
</template>

<style scoped>
.layout { flex: 1 1 0 !important; display: grid; grid-template-columns: minmax(0, 1fr) 440px; gap: 12px; min-height: 0; }
.side { overflow-y: auto; min-height: 0; }
.meta { font-size: 12px; color: var(--muted); margin-bottom: 9px; }
.buttons { display: flex; gap: 8px; margin-top: 10px; }
@media (max-width: 1100px) {
  .layout { grid-template-columns: minmax(0, 1fr); height: auto; }
  .layout > :first-child { height: 60vh; }
  .side { overflow: visible; }
}
</style>
