<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { codeName } from '../../stores/session'
import { toast, toastError, toastOk } from '../../stores/toast'

const props = defineProps({ planId: { type: Number, required: true }, canWrite: Boolean })
const emit = defineEmits(['changed', 'open-drawing'])

const data = ref({ blockers: [], links: [], available: [] })
const drawingId = ref('')
const required = ref(true)
const url = `/plans/${props.planId}/drawings`

const blockerText = computed(() =>
  data.value.blockers.map((item) => `${item.drawing_no}(${codeName('DWGSTAT', item.dwg_status)})`).join(', '))

async function load() {
  try {
    data.value = await api.get(url)
  } catch (error) {
    toastError(error)
  }
}

async function add() {
  if (!drawingId.value) {
    toast('도면을 선택하세요.', 'error')
    return
  }
  try {
    data.value = await api.post(url, { drawing_id: Number(drawingId.value), required: required.value })
    drawingId.value = ''
    toastOk('도면이 연계되었습니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

async function remove(link) {
  try {
    await api.del(`${url}/${link.drawing_id}`)
    toastOk('연계가 해제되었습니다.')
    await load()
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="links">
    <div v-if="data.blockers.length" class="note warn">📐 도면 대기: 필수 도면 <b>{{ blockerText }}</b> 미배포 → 착수 불가</div>
    <div class="ttl"><b>연계 도면</b> (필수 도면은 배포 전 착수 불가)</div>
    <div class="tw grow">
      <table class="t">
        <thead><tr><th>도면번호</th><th>상태</th><th>필수</th><th /></tr></thead>
        <tbody>
          <tr v-for="link in data.links" :key="link.drawing_id">
            <td><button class="lnk" @click="emit('open-drawing', link.drawing_id)">{{ link.drawing_no }}</button></td>
            <td>
              <span class="bdg" :class="link.dwg_status">{{ codeName('DWGSTAT', link.dwg_status) }}</span>
              <span v-if="!link.has_issued" class="bdg warn">미배포</span>
            </td>
            <td>{{ link.required ? '필수' : '참고' }}</td>
            <td><button class="btn sm danger" :disabled="!canWrite" @click="remove(link)">해제</button></td>
          </tr>
          <tr v-if="!data.links.length"><td colspan="4" class="empty">연계된 도면이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="add">
      <select v-model="drawingId" class="input" :disabled="!canWrite">
        <option value="">도면 선택</option>
        <option v-for="item in data.available" :key="item.drawing_id" :value="item.drawing_id">{{ item.drawing_no }} {{ item.drawing_nm }}</option>
      </select>
      <label class="check"><input v-model="required" type="checkbox" :disabled="!canWrite" />필수</label>
      <button class="btn" :disabled="!canWrite" @click="add">+ 연계</button>
    </div>
  </div>
</template>

<style scoped>
.links { display: flex; flex-direction: column; min-width: 0; height: 100%; }
.note { padding: 7px 10px; margin-bottom: 6px; }
.ttl { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.ttl b { color: var(--ink); }
.grow { flex: 1; min-height: 100px; }
.add { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.add .input { flex: 1; min-width: 0; }
.lnk { background: none; border: 0; padding: 0; color: var(--pri-d); cursor: pointer; }
.t td { padding-top: 5px; padding-bottom: 5px; }
.bdg + .bdg { margin-left: 2px; }
</style>
