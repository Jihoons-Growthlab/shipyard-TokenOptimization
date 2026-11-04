<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import CodeSelect from '../../components/CodeSelect.vue'
import { toastError, toastOk } from '../../stores/toast'

const props = defineProps({ hullNo: { type: String, default: null }, canWrite: Boolean })
const emit = defineEmits(['loaded', 'created', 'changed', 'deleted'])

const blank = () => ({
  hull_no: '', hull_nm: '', ship_type: '', hull_status: 'PLAN', owner_nm: '', class_society: '',
  length_m: '', breadth_m: '', depth_m: '', dead_weight: '', dock_no: '', contract_dt: '', delivery_dt: '',
  use_yn: true, remark: '',
})
const form = ref(blank())
const loading = ref(Boolean(props.hullNo))
const isNew = computed(() => !props.hullNo)
const locked = computed(() => loading.value || !props.canWrite)

function apply(hull) {
  form.value = Object.fromEntries(Object.keys(blank()).map((key) => [key, hull[key] ?? '']))
}

onMounted(async () => {
  if (isNew.value) return
  try {
    const hull = await api.get(`/hulls/${props.hullNo}`)
    apply(hull)
    emit('loaded', hull)
    loading.value = false
  } catch (error) {
    toastError(error)
  }
})

function payload() {
  const toNumber = (value) => (value === '' ? null : Number(value))
  return {
    ...form.value,
    length_m: toNumber(form.value.length_m), breadth_m: toNumber(form.value.breadth_m),
    depth_m: toNumber(form.value.depth_m), dead_weight: toNumber(form.value.dead_weight),
  }
}

async function save() {
  try {
    if (isNew.value) {
      emit('created', await api.post('/hulls', payload()))
      toastOk('호선이 등록되었습니다.')
    } else {
      const hull = await api.patch(`/hulls/${props.hullNo}`, payload())
      apply(hull)
      emit('loaded', hull)
      emit('changed')
      toastOk('저장되었습니다.')
    }
  } catch (error) {
    toastError(error)
  }
}

async function remove() {
  if (!window.confirm(`호선 ${props.hullNo} 및 하위 데이터(블록·공정·도면)를 모두 삭제합니다. 계속할까요?`)) return
  try {
    await api.del(`/hulls/${props.hullNo}`)
    toastOk('삭제되었습니다.')
    emit('deleted')
  } catch (error) {
    toastError(error)
  }
}
</script>

<template>
  <div class="card">
    <form class="fg c4" @submit.prevent="save">
      <div class="field"><label>호선번호 *</label><input v-model="form.hull_no" :readonly="!isNew" :disabled="locked" /></div>
      <div class="field span2"><label>호선명</label><input v-model="form.hull_nm" :disabled="locked" /></div>
      <div class="field"><label>선종</label><CodeSelect v-model="form.ship_type" group="SHIPTYPE" empty="선택" :disabled="locked" /></div>
      <div class="field"><label>상태</label><CodeSelect v-model="form.hull_status" group="HULLSTAT" :disabled="locked" /></div>
      <div class="field span2"><label>선주</label><input v-model="form.owner_nm" :disabled="locked" /></div>
      <div class="field"><label>선급</label><input v-model="form.class_society" :disabled="locked" /></div>
      <div class="field"><label>전장(m)</label><input v-model="form.length_m" type="number" step="any" :disabled="locked" /></div>
      <div class="field"><label>선폭(m)</label><input v-model="form.breadth_m" type="number" step="any" :disabled="locked" /></div>
      <div class="field"><label>선심(m)</label><input v-model="form.depth_m" type="number" step="any" :disabled="locked" /></div>
      <div class="field"><label>재화중량(DWT)</label><input v-model="form.dead_weight" type="number" step="any" :disabled="locked" /></div>
      <div class="field"><label>도크/건조장소</label><input v-model="form.dock_no" :disabled="locked" /></div>
      <div class="field"><label>계약일</label><input v-model="form.contract_dt" type="date" :disabled="locked" /></div>
      <div class="field"><label>인도 예정일</label><input v-model="form.delivery_dt" type="date" :disabled="locked" /></div>
      <div class="field"><label>사용여부</label><label class="check"><input v-model="form.use_yn" type="checkbox" :disabled="locked" />사용</label></div>
      <div class="field span4"><label>비고</label><input v-model="form.remark" maxlength="500" :disabled="locked" /></div>
      <div class="span4 actions">
        <button class="btn pri" :disabled="locked">저장</button>
        <button v-if="!isNew" class="btn danger" type="button" :disabled="locked" @click="remove">삭제</button>
        <span class="muted">삭제 시 블록·공정·도면이 함께 삭제됩니다(FK CASCADE).</span>
      </div>
    </form>
  </div>
</template>

<style scoped>
.actions { display: flex; align-items: center; gap: 8px; font-size: 12px; }
</style>
