<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import { pdfError } from '../../lib/pdf'
import { codeName } from '../../stores/session'
import { toast, toastError, toastOk } from '../../stores/toast'
import { issueRevision, uploadPdf } from './drawingApi'

const props = defineProps({
  drawing: { type: Object, required: true },
  revNo: { type: Number, required: true },
  canWrite: Boolean,
})
const emit = defineEmits(['update:revNo', 'changed'])

const users = ref([])
const changeDesc = ref('')
const file = ref(null)
const fileInput = ref(null)
const reviewer = ref('')
const approver = ref('')

const latest = computed(() => props.drawing.revisions[0])
const nextRev = computed(() => latest.value.rev_no + 1)
const base = computed(() => `/drawings/${props.drawing.drawing_id}/revisions`)

function fileNote(rev) {
  if (!rev.file_nm) return '파일 없음'
  return rev.has_file ? rev.file_nm : `${rev.file_nm} (미업로드)`
}

const hasUser = (emp) => users.value.some((user) => user.emp_no === emp)

onMounted(async () => {
  try {
    users.value = await api.get('/users/options')
    reviewer.value = hasUser('lee.dwg') ? 'lee.dwg' : ''
    approver.value = hasUser('admin') ? 'admin' : ''
  } catch (error) {
    toastError(error)
  }
})

watch(() => props.drawing.drawing_id, () => { changeDesc.value = '' })

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

async function createRevision() {
  const revNo = nextRev.value
  try {
    await api.post(base.value, { change_desc: changeDesc.value })
    if (file.value) await uploadPdf(props.drawing.drawing_id, revNo, file.value)
    toastOk(`Rev${revNo} 작성중으로 생성되었습니다.`)
  } catch (error) {
    toastError(error)
    if (!error.status || error.code === 'VALIDATION_ERROR' || error.code === 'INVALID_REV_STATE') return
  }
  changeDesc.value = ''
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
  emit('update:revNo', revNo)
  emit('changed')
}

async function requestApproval() {
  try {
    await api.post(`${base.value}/${latest.value.rev_no}/request-approval`, { reviewer_emp_no: reviewer.value, approver_emp_no: approver.value })
    toastOk('결재가 요청되었습니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

async function issue() {
  try {
    await issueRevision(props.drawing.drawing_id, latest.value.rev_no)
    toastOk('도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}
</script>

<template>
  <section class="card">
    <h3>리비전 이력 <span class="bdg">{{ drawing.revisions.length }}</span></h3>
    <div class="tw hist">
      <table class="t fixed">
        <colgroup><col style="width: 92px" /><col style="width: 62px" /><col /><col style="width: 92px" /></colgroup>
        <thead><tr><th>Rev</th><th>상태</th><th>변경사유</th><th>배포일</th></tr></thead>
        <tbody>
          <tr v-for="rev in drawing.revisions" :key="rev.rev_no" :class="{ selected: rev.rev_no === revNo }">
            <td><b>Rev{{ rev.rev_no }}</b> <button class="lnk" @click="emit('update:revNo', rev.rev_no)">보기</button></td>
            <td class="st"><span class="bdg" :class="rev.rev_status">{{ codeName('DWGSTAT', rev.rev_status) }}</span></td>
            <td class="cut"><div class="desc">{{ rev.change_desc }}</div><small :title="fileNote(rev)">{{ fileNote(rev) }}</small></td>
            <td>{{ rev.issue_dt || '미배포' }}<small>{{ rev.author_nm }}</small></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="canWrite" class="work">
      <template v-if="latest.rev_status === 'ISSUED' || latest.rev_status === 'OBSOLETE'">
        <div class="field"><label>신규 Rev{{ nextRev }} 개정 사유</label><input v-model="changeDesc" maxlength="1000" /></div>
        <div class="row">
          <div class="field"><label>도면 파일 (PDF, 선택)</label><input ref="fileInput" class="file" type="file" accept=".pdf,application/pdf" @change="pick" /></div>
          <button class="btn pri" @click="createRevision">신규 Rev 작성</button>
        </div>
      </template>
      <template v-else-if="latest.rev_status === 'DRAFT'">
        <div class="note warn">Rev{{ latest.rev_no }} 작성중입니다. 검토자/승인자를 지정해 결재를 요청하세요.</div>
        <div class="fg c2">
          <div class="field"><label>1단계 검토자</label>
            <select v-model="reviewer"><option value="">-</option><option v-for="user in users" :key="user.emp_no" :value="user.emp_no">{{ user.display_name }} ({{ user.emp_no }})</option></select>
          </div>
          <div class="field"><label>2단계 승인자</label>
            <select v-model="approver"><option value="">-</option><option v-for="user in users" :key="user.emp_no" :value="user.emp_no">{{ user.display_name }} ({{ user.emp_no }})</option></select>
          </div>
        </div>
        <button class="btn pri action" @click="requestApproval">결재 요청</button>
      </template>
      <div v-else-if="latest.rev_status === 'REVIEW'" class="note warn">Rev{{ latest.rev_no }} 결재 진행중입니다. 결재자는 [결재함]에서 처리합니다.</div>
      <template v-else-if="latest.rev_status === 'APPROVED'">
        <div class="note ok">Rev{{ latest.rev_no }} 승인 완료 — 배포하면 연계 공정의 도면 게이트가 열립니다.</div>
        <button class="btn ok" @click="issue">Rev{{ latest.rev_no }} 배포</button>
      </template>
    </div>
  </section>
</template>

<style scoped>
.hist { max-height: 190px; }
.fixed { table-layout: fixed; }
.fixed td { vertical-align: middle; white-space: nowrap; padding: 5px 8px; }
.st { padding-left: 2px !important; }
.st .bdg { padding: 1px 6px; }
small { display: block; font-size: 11.5px; color: var(--muted); }
.cut small, .desc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lnk { background: none; border: 0; padding: 0; color: var(--pri-d); cursor: pointer; }
.work { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.note { margin: 0; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: end; }
.row .btn { justify-self: start; }
.field input.file { padding: 3px 6px; }
.action, .btn.ok { align-self: flex-start; }
</style>
