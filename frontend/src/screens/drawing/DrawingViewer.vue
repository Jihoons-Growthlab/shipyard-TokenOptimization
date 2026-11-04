<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../../api/client'
import { useLatest } from '../../composables/useLatest'
import { pdfError } from '../../lib/pdf'
import { codeName } from '../../stores/session'
import { toast, toastError, toastOk } from '../../stores/toast'
import { pdfUrl, uploadPdf } from './drawingApi'

const props = defineProps({
  drawing: { type: Object, required: true },
  revNo: { type: Number, required: true },
  canWrite: Boolean,
})
const emit = defineEmits(['update:revNo', 'changed'])

const blobUrl = ref(null)
const latest = useLatest()

const revision = computed(() => props.drawing.revisions.find((rev) => rev.rev_no === props.revNo))
const isDraft = computed(() => revision.value?.rev_status === 'DRAFT')
const statusName = (status) => codeName('DWGSTAT', status)

function setBlob(url) {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  blobUrl.value = url
}

async function loadPdf() {
  const seq = latest.next()
  setBlob(null)
  if (!revision.value?.has_file) return
  try {
    const response = await api.get(pdfUrl(props.drawing.drawing_id, props.revNo), { raw: true })
    const blob = await response.blob()
    if (latest.isCurrent(seq)) setBlob(URL.createObjectURL(blob))
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

watch(() => [props.drawing.drawing_id, props.revNo, revision.value?.has_file, revision.value?.file_nm], loadPdf, { immediate: true })
onBeforeUnmount(() => {
  latest.next()
  setBlob(null)
})

async function upload(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  const problem = pdfError(file)
  if (problem) {
    toast(problem, 'error')
    return
  }
  try {
    await uploadPdf(props.drawing.drawing_id, props.revNo, file)
    toastOk(`Rev${props.revNo}에 PDF를 업로드했습니다.`)
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

async function removeFile() {
  try {
    await api.del(pdfUrl(props.drawing.drawing_id, props.revNo))
    toastOk('파일을 삭제했습니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

function openWindow() {
  if (blobUrl.value) window.open(blobUrl.value, '_blank')
  else toast('표시 중인 PDF가 없습니다.', 'error')
}
</script>

<template>
  <section class="card viewer">
    <h3>도면 뷰어 (PDF)<small>작성중(DRAFT) 리비전만 업로드·교체·삭제할 수 있습니다.</small></h3>
    <div class="tools">
      <select class="input rev" :value="revNo" aria-label="리비전" @change="emit('update:revNo', Number($event.target.value))">
        <option v-for="rev in drawing.revisions" :key="rev.rev_no" :value="rev.rev_no">Rev{{ rev.rev_no }} ({{ statusName(rev.rev_status) }})</option>
      </select>
      <span class="name">{{ revision?.file_nm || '파일 없음' }}</span>
      <span v-if="revision?.has_file" class="bdg ok">업로드 파일</span>
      <span v-else class="bdg warn">샘플 PDF (미업로드)</span>
      <span class="gap" />
      <template v-if="canWrite">
        <input class="input file" type="file" accept=".pdf,application/pdf" :disabled="!isDraft" aria-label="PDF 파일" @change="upload" />
        <button class="btn" :disabled="!isDraft || !revision?.has_file" @click="removeFile">파일 삭제</button>
      </template>
      <button class="btn" @click="openWindow">새 창으로 열기</button>
    </div>
    <div class="body">
      <iframe v-if="blobUrl" :src="`${blobUrl}#view=FitH`" title="도면 PDF" />
      <div v-else class="sample">
        <b>샘플 PDF (미업로드)</b>
        <span>{{ drawing.drawing_no }} · Rev{{ revNo }} · {{ statusName(revision?.rev_status) }}</span>
        <small>이 리비전에는 업로드된 도면 파일이 없습니다.</small>
      </div>
    </div>
  </section>
</template>

<style scoped>
.viewer { display: flex; flex-direction: column; margin: 0; min-height: 0; min-width: 0; }
.viewer > h3 small { font-weight: 400; font-size: 12px; color: var(--muted); }
.tools { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; min-width: 0; }
.rev { width: 110px; flex: none; }
.name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.gap { flex: 1; }
.file { width: 230px; flex: none; padding: 3px 6px; }
.body { flex: 1; min-height: 0; background: #525659; border-radius: 4px; border: 1px solid var(--line); display: flex; }
iframe { width: 100%; height: 100%; border: 0; }
.sample { margin: auto; color: #fff; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.sample small { font-size: 11px; }
</style>
