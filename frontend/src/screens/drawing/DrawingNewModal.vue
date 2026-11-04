<script setup>
import { reactive, ref } from 'vue'
import { api } from '../../api/client'
import ModalBox from '../../components/ModalBox.vue'
import { pdfError } from '../../lib/pdf'
import { session } from '../../stores/session'
import { toast, toastError, toastOk } from '../../stores/toast'
import DrawingForm from './DrawingForm.vue'
import { uploadPdf } from './drawingApi'

const props = defineProps({ hullNo: { type: String, default: '' } })
const emit = defineEmits(['created', 'close'])

const form = reactive({
  drawing_no: '', drawing_nm: '', discipline: 'HULL', hull_no: props.hullNo, block_id: '',
  designer_emp_no: session.user?.emp_no ?? '',
})
const file = ref(null)
const busy = ref(false)

function pick(event) {
  const chosen = event.target.files[0] ?? null
  const problem = chosen && pdfError(chosen)
  if (problem) {
    toast(problem, 'error')
    event.target.value = ''
    file.value = null
    return
  }
  file.value = chosen
}

async function save() {
  busy.value = true
  try {
    const created = await api.post('/drawings', { ...form, block_id: form.block_id || null })
    let suffix = ''
    if (file.value) {
      try {
        await uploadPdf(created.drawing_id, 0, file.value)
        suffix = ' PDF 첨부됨.'
      } catch (error) {
        suffix = ` (PDF 저장 실패: ${error.message})`
      }
    }
    toastOk(`도면이 등록되었습니다. (Rev0 작성중)${suffix}`)
    emit('created', created.drawing_id)
  } catch (error) {
    toastError(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <ModalBox title="도면 등록" size="large" @close="emit('close')">
    <p class="desc">신규 도면은 Rev0(작성중)으로 생성됩니다. PDF는 지금 첨부하거나 등록 후 뷰어에서 업로드할 수 있습니다.</p>
    <form class="card" @submit.prevent="save">
      <DrawingForm :form="form" is-new>
        <div class="field span2"><label>도면 파일 (PDF, 선택)</label><input class="file" type="file" accept=".pdf,application/pdf" @change="pick" /></div>
      </DrawingForm>
      <button class="btn pri save" :disabled="busy">저장</button>
    </form>
  </ModalBox>
</template>

<style scoped>
.desc { font-size: 12px; color: var(--muted); margin-bottom: 10px; }
.save { margin-top: 10px; }
.card { margin-bottom: 0; }
.field input.file { padding: 3px 6px; }
</style>
