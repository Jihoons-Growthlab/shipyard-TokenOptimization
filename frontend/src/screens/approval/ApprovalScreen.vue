<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import ScreenHead from '../../components/ScreenHead.vue'
import { session } from '../../stores/session'
import { toast, toastError, toastOk } from '../../stores/toast'
import DrawingDetailModal from '../drawing/DrawingDetailModal.vue'
import { issueRevision, RESULT_BADGES, STEP_NAMES } from '../drawing/drawingApi'
import { screenProps } from '../props'

const props = defineProps(screenProps)

const inbox = ref({ waiting: [], ready: [], can_issue: false })
const history = ref([])
const comments = ref({})
const busy = ref(false)
const detailId = ref(null)

const desc = computed(() => `${session.user?.display_name ?? ''} 님의 결재 대기와 배포 대기 도면입니다.`)

async function load() {
  try {
    const [box, recent] = await Promise.all([api.get('/approvals/inbox'), api.get('/approvals/history')])
    inbox.value = box
    history.value = recent
  } catch (error) {
    toastError(error)
  }
}

async function run(action, message) {
  busy.value = true
  try {
    await action()
    toastOk(message)
  } catch (error) {
    toastError(error)
  } finally {
    await load()
    busy.value = false
  }
}

function decide(item, result) {
  const comment = comments.value[item.approval_id] ?? ''
  if (result === 'REJECT' && !comment.trim()) {
    toast('반려 시 의견을 입력하세요.', 'error')
    return
  }
  const message = result === 'APPROVE' ? '승인했습니다.' : '반려했습니다. 도면은 작성중으로 되돌려집니다.'
  run(() => api.post(`/approvals/${item.approval_id}/decision`, { result, comment }), message)
}

const issue = (item) =>
  run(() => issueRevision(item.drawing_id, item.rev_no), '도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')

onMounted(load)
watch(() => [props.tick, props.active], load)
</script>

<template>
  <ScreenHead title="도면 결재함" :desc="desc" :readonly="!canWrite" />
  <section class="card">
    <h3>내 결재 대기 <span class="bdg warn">{{ inbox.waiting.length }}</span></h3>
    <div class="tw">
      <table class="t">
        <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>단계</th><th>변경사유</th><th>의견</th><th v-if="canWrite" /></tr></thead>
        <tbody>
          <tr v-for="item in inbox.waiting" :key="item.approval_id">
            <td><button class="lnk" @click="detailId = item.drawing_id">{{ item.drawing_no }}</button></td>
            <td>{{ item.drawing_nm }}</td>
            <td>Rev{{ item.rev_no }}</td>
            <td>{{ STEP_NAMES[item.step_no] }}</td>
            <td class="wrap">{{ item.change_desc }}</td>
            <td><input v-model="comments[item.approval_id]" class="input cmt" placeholder="의견 (반려 시 필수)" maxlength="1000" :disabled="!canWrite" /></td>
            <td v-if="canWrite" class="btns">
              <button class="btn sm ok" :disabled="busy" @click="decide(item, 'APPROVE')">승인</button>
              <button class="btn sm danger" :disabled="busy" @click="decide(item, 'REJECT')">반려</button>
            </td>
          </tr>
          <tr v-if="!inbox.waiting.length"><td colspan="7" class="empty">결재 대기 건이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
  <section class="card">
    <h3>배포 대기 (승인 완료) <span class="bdg info">{{ inbox.ready.length }}</span></h3>
    <div class="tw">
      <table class="t">
        <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>배포 시 착수 가능해질 수 있는 공정</th><th v-if="inbox.can_issue" /></tr></thead>
        <tbody>
          <tr v-for="item in inbox.ready" :key="item.drawing_id">
            <td><button class="lnk" @click="detailId = item.drawing_id">{{ item.drawing_no }}</button></td>
            <td>{{ item.drawing_nm }}</td>
            <td>Rev{{ item.rev_no }}</td>
            <td class="wrap">{{ item.effect_plans.join(', ') || '-' }}</td>
            <td v-if="inbox.can_issue" class="btns"><button class="btn sm ok" :disabled="busy" @click="issue(item)">배포</button></td>
          </tr>
          <tr v-if="!inbox.ready.length"><td colspan="5" class="empty">배포 대기 도면이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
  <section class="card">
    <h3>최근 결재 이력</h3>
    <div class="tw">
      <table class="t">
        <thead><tr><th>일시</th><th>도면번호</th><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th><th>의견</th></tr></thead>
        <tbody>
          <tr v-for="item in history" :key="item.approval_id">
            <td>{{ item.act_dt }}</td>
            <td>{{ item.drawing_no }}</td>
            <td>Rev{{ item.rev_no }}</td>
            <td>{{ STEP_NAMES[item.step_no] }}</td>
            <td>{{ item.approver_nm }}</td>
            <td><span class="bdg" :class="RESULT_BADGES[item.result][0]">{{ RESULT_BADGES[item.result][1] }}</span></td>
            <td class="wrap">{{ item.comment }}</td>
          </tr>
          <tr v-if="!history.length"><td colspan="7" class="empty">결재 이력이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
  <DrawingDetailModal v-if="detailId" :drawing-id="detailId" @changed="load" @close="detailId = null" />
</template>

<style scoped>
.lnk { background: none; border: 0; padding: 0; color: var(--pri-d); cursor: pointer; }
.input.cmt { width: 148px; }
.btns { width: 180px; }
.btns .btn + .btn { margin-left: 4px; }
</style>
