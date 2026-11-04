<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import ScreenHead from '../../components/ScreenHead.vue'
import { useLatest } from '../../composables/useLatest'
import { session } from '../../stores/session'
import { refreshAccount } from '../../stores/shell'
import { toast, toastError, toastOk } from '../../stores/toast'
import { screenProps } from '../props'

const props = defineProps(screenProps)

const STATUSES = [['pending', '승인대기', 'warn'], ['approved', '승인', 'ok'], ['rejected', '반려', 'bad'], ['disabled', '중지', '']]
const statusOf = (code) => STATUSES.find((item) => item[0] === code) ?? [code, code, '']

const blankFilters = () => ({ status: '', q: '' })
const blankForm = () => ({
  last_name: '', first_name: '', birth_date: '', phone: '', email: '', emp_no: '', password: '',
  status: 'approved', group: '', totp_enabled: false, created_at: '-',
})
const filters = ref(blankFilters())
const list = ref({ users: [], total: 0, pending: 0 })
const groups = ref([])
const mode = ref(null)
const selected = ref(null)
const form = ref(blankForm())
const latest = useLatest()

const heading = computed(() => {
  if (mode.value === 'edit') return `회원 수정 — ${selected.value.display_name}`
  return mode.value === 'new' ? '회원 등록' : '입력 / 수정'
})
const editing = computed(() => mode.value === 'edit')
const isSelf = computed(() => editing.value && selected.value.emp_no === session.user?.emp_no)

async function load() {
  const seq = latest.next()
  try {
    const result = await api.get('/users', { query: filters.value })
    if (latest.isCurrent(seq)) list.value = result
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

function reset() {
  filters.value = blankFilters()
  load()
}

function select(user) {
  selected.value = user
  mode.value = 'edit'
  const { last_name, first_name, birth_date, phone, email, emp_no, status, totp_enabled, created_at } = user
  form.value = {
    last_name, first_name, birth_date, phone, email, emp_no, status, totp_enabled, created_at,
    password: '', group: user.groups[0]?.code ?? '',
  }
}

function startNew() {
  selected.value = null
  mode.value = 'new'
  form.value = blankForm()
}

function clear() {
  selected.value = null
  mode.value = null
}

async function afterChange(emp_no) {
  await load()
  const fresh = list.value.users.find((user) => user.emp_no === emp_no)
  if (fresh) select(fresh)
  else clear()
}

async function save() {
  const { group, created_at, ...fields } = form.value
  const body = { ...fields, groups: group ? [group] : [] }
  try {
    if (editing.value) {
      await api.patch(`/users/${selected.value.emp_no}`, body)
      if (isSelf.value) await refreshAccount()
    } else {
      await api.post('/users', body)
    }
    toastOk('저장되었습니다.')
    await afterChange(fields.emp_no)
  } catch (error) {
    toastError(error)
  }
}

async function remove() {
  if (isSelf.value) {
    toast('로그인 중인 본인 계정은 삭제할 수 없습니다.', 'error')
    return
  }
  if (!window.confirm(`회원 ${selected.value.emp_no} 을(를) 삭제합니다.`)) return
  try {
    await api.del(`/users/${selected.value.emp_no}`)
    toastOk('삭제되었습니다.')
    clear()
    await load()
  } catch (error) {
    toastError(error)
  }
}

async function approve() {
  const user = selected.value
  try {
    await api.post(`/users/${user.emp_no}/approve`, { groups: form.value.group ? [form.value.group] : [] })
    toastOk(`${user.display_name} 님의 가입을 승인했습니다.`)
    await afterChange(user.emp_no)
  } catch (error) {
    toastError(error)
  }
}

onMounted(async () => {
  load()
  try {
    groups.value = await api.get('/auth-groups')
  } catch (error) {
    toastError(error)
  }
})
watch(() => props.tick, load)
</script>

<template>
  <div class="screen">
    <ScreenHead :title="title" desc="상단 목록 / 하단 입력·수정 (CRUD)" :readonly="!canWrite" />
    <div class="split">
      <div class="top">
        <form class="filters" @submit.prevent="load">
          <select v-model="filters.status" class="input" aria-label="상태">
            <option value="">상태 전체</option>
            <option v-for="[code, name] in STATUSES" :key="code" :value="code">{{ name }}</option>
          </select>
          <input v-model="filters.q" class="input" placeholder="아이디/이름/이메일/전화" />
          <button class="btn pri">조회</button>
          <button class="btn" type="button" @click="reset">초기화</button>
          <span class="right muted count">{{ list.total }}명 · 승인대기 {{ list.pending }}명</span>
        </form>
        <div class="tw grow">
          <table class="t">
            <thead>
              <tr><th>아이디</th><th>이름</th><th>이메일</th><th>전화번호</th><th>생년월일</th><th>상태</th><th>2차인증</th><th>권한그룹</th><th>가입일</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="user in list.users" :key="user.emp_no" class="click"
                :class="{ selected: selected?.emp_no === user.emp_no }" @click="select(user)"
              >
                <td><b class="id">{{ user.emp_no }}</b></td>
                <td>{{ user.display_name }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.phone }}</td>
                <td>{{ user.birth_date }}</td>
                <td><span class="bdg" :class="statusOf(user.status)[2]">{{ statusOf(user.status)[1] }}</span></td>
                <td>{{ user.totp_enabled ? '사용' : '-' }}</td>
                <td>{{ user.groups.map((group) => group.name).join(', ') || '-' }}</td>
                <td>{{ user.created_at }}</td>
              </tr>
              <tr v-if="!list.users.length"><td colspan="9" class="empty">조회된 회원이 없습니다.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <section class="card bottom">
        <h3>{{ heading }}</h3>
        <p v-if="!mode" class="muted">목록에서 회원을 선택하거나 [신규]를 누르세요.</p>
        <form v-else id="user-form" class="fg c4" @submit.prevent="save">
          <div class="field"><label>성 *</label><input v-model="form.last_name" maxlength="50" /></div>
          <div class="field"><label>이름 *</label><input v-model="form.first_name" maxlength="50" /></div>
          <div class="field"><label>생년월일 *</label><input v-model="form.birth_date" type="date" /></div>
          <div class="field"><label>전화번호 *</label><input v-model="form.phone" placeholder="010-0000-0000" /></div>
          <div class="field span2"><label>이메일 *</label><input v-model="form.email" /></div>
          <div class="field"><label>아이디 *</label><input v-model="form.emp_no" :readonly="editing" /></div>
          <div class="field"><label>{{ editing ? '비밀번호 (변경 시만 입력)' : '비밀번호 *' }}</label><input v-model="form.password" type="password" placeholder="8자 이상" autocomplete="new-password" /></div>
          <div class="field"><label>상태</label>
            <select v-model="form.status"><option v-for="[code, name] in STATUSES" :key="code" :value="code">{{ name }}</option></select>
          </div>
          <div class="field"><label>권한 그룹</label>
            <select v-model="form.group"><option value="">없음</option><option v-for="group in groups" :key="group.code" :value="group.code">{{ group.name }}</option></select>
          </div>
          <div class="field"><label>구글 2차인증</label><label class="check"><input v-model="form.totp_enabled" type="checkbox" />사용 (등록된 사용자만)</label></div>
          <div class="field"><label>가입일</label><input :value="form.created_at" readonly /></div>
        </form>
        <div class="buttons">
          <button class="btn" type="button" @click="startNew">신규</button>
          <button class="btn pri" type="submit" form="user-form" :disabled="!mode">저장</button>
          <button class="btn danger" type="button" :disabled="!editing || isSelf" @click="remove">삭제</button>
          <button v-if="editing && selected.status === 'pending'" class="btn ok" type="button" @click="approve">가입 승인</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.screen { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.split { flex: 1; min-height: 0; display: grid; grid-template-rows: minmax(0, 1fr) minmax(0, 1fr); gap: 10px; }
.top { display: flex; flex-direction: column; min-height: 0; }
.grow { flex: 1; min-height: 0; }
.count { font-size: 12px; }
.id { font-size: 13.5px; }
.bottom { margin: 0; overflow: auto; }
.buttons { display: flex; gap: 8px; margin-top: 12px; }
</style>
