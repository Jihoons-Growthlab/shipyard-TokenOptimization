<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import scene from '../components/auth-scene.svg?raw'
import { startSession } from '../stores/session'
import { toast } from '../stores/toast'

const router = useRouter()
const mode = ref('login')
const error = ref('')
const busy = ref(false)
const empNo = ref('')
const password = ref('')
const otpCode = ref('')
const otpToken = ref('')
const blank = () => ({
  last_name: '', first_name: '', birth_date: '', phone: '', email: '', emp_no: '', password: '', password_confirm: '',
})
const signup = ref(blank())
const firstInput = ref(null)

const HEADS = {
  login: ['SWP SHIPYARD', '조선소 통합관리', '호선 · 공정 · 도면 관리 시스템'],
  otp: ['2-STEP VERIFICATION', '구글 2차 인증', 'Google Authenticator 앱에 표시된 6자리 코드를 입력하세요.'],
  signup: ['SIGN UP', '회원가입', '가입 후 관리자 승인이 완료되면 로그인할 수 있습니다.'],
}
const head = computed(() => HEADS[mode.value])
const SIGNUP_FIELDS = [
  ['last_name', '성', 'text'], ['first_name', '이름', 'text'], ['birth_date', '생년월일', 'date'],
  ['phone', '전화번호', 'tel', '010-0000-0000'], ['email', '이메일', 'email'], ['emp_no', '아이디', 'text'],
  ['password', '비밀번호', 'password'], ['password_confirm', '비밀번호 확인', 'password'],
]

function go(next) {
  mode.value = next
  error.value = ''
  otpCode.value = ''
}

watch(mode, () => nextTick(() => firstInput.value?.focus?.()), { immediate: false })

async function run(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function enter(result) {
  startSession(result)
  router.replace('/')
}

const submitLogin = () =>
  run(async () => {
    const result = await api.post('/auth/login', { emp_no: empNo.value, password: password.value })
    if (result.otp_required) {
      otpToken.value = result.otp_token
      password.value = ''
      go('otp')
    } else enter(result)
  })

const submitOtp = () =>
  run(async () => enter(await api.post('/auth/otp/verify', { code: otpCode.value }, { token: otpToken.value })))

const submitSignup = () =>
  run(async () => {
    await api.post('/auth/register', signup.value)
    signup.value = blank()
    go('login')
    toast('가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.', 'success')
  })
</script>

<template>
  <div class="auth">
    <div class="scene" v-html="scene" />
    <section class="intro">
      <div class="brand">⚓ SWP SHIPYARD</div>
      <h2>설계부터 인도까지,<br />조선소 운영을 한곳에서</h2>
      <ul>
        <li><b>호선</b><span>호선별 진척률과 인도 일정을 한눈에</span></li>
        <li><b>공정</b><span>간트 계획부터 일별 실적까지</span></li>
        <li><b>도면</b><span>리비전·결재·배포 이력 관리</span></li>
      </ul>
    </section>

    <section class="auth-card" :class="{ wide: mode === 'signup' }">
      <div class="logo">{{ head[0] }}</div>
      <h1>{{ head[1] }}</h1>
      <p class="sub">{{ head[2] }}</p>

      <form v-if="mode === 'login'" @submit.prevent="submitLogin">
        <div class="field"><label for="emp">아이디</label><input id="emp" ref="firstInput" v-model="empNo" autocomplete="username" autofocus /></div>
        <div class="field"><label for="pw">비밀번호</label><input id="pw" v-model="password" type="password" autocomplete="current-password" /></div>
        <p class="auth-err">{{ error }}</p>
        <button class="btn pri submit" :disabled="busy">로그인</button>
        <div class="foot"><a href="#" @click.prevent="go('signup')">회원가입</a><span>구글 2차 인증 사용 계정은 다음 단계에서 OTP 입력</span></div>
      </form>

      <form v-else-if="mode === 'otp'" @submit.prevent="submitOtp">
        <div class="field"><label for="otp">인증 코드</label><input id="otp" ref="firstInput" v-model="otpCode" class="otp" maxlength="6" inputmode="numeric" autocomplete="one-time-code" /></div>
        <p class="auth-err">{{ error }}</p>
        <button class="btn pri submit" :disabled="busy">확인</button>
        <div class="foot"><a href="#" @click.prevent="go('login')">← 로그인으로</a></div>
      </form>

      <form v-else @submit.prevent="submitSignup">
        <div class="grid">
          <div v-for="[key, label, type, placeholder] in SIGNUP_FIELDS" :key="key" class="field">
            <label :for="key">{{ label }}</label>
            <input :id="key" v-model="signup[key]" :type="type" :placeholder="placeholder" />
          </div>
        </div>
        <p class="auth-err">{{ error }}</p>
        <button class="btn pri submit" :disabled="busy">가입 신청</button>
        <div class="foot"><a href="#" @click.prevent="go('login')">← 로그인으로</a></div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.auth {
  position: relative; min-height: 100%; background: #060f22; overflow: hidden; display: grid;
  grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 48px; padding: 40px clamp(28px, 7vw, 120px);
}
.scene { position: absolute; inset: 0; pointer-events: none; }
.scene :deep(svg) { width: 100%; height: 100%; display: block; }
.intro { position: relative; z-index: 1; margin-bottom: 22vh; max-width: 520px; color: #fff; }
.intro::before {
  content: ''; position: absolute; inset: -200px; z-index: -1;
  background: radial-gradient(closest-side, rgba(6, 15, 34, .75), rgba(6, 15, 34, .42) 65%, rgba(6, 15, 34, 0));
}
.brand { font-size: 13px; font-weight: 700; letter-spacing: 3px; color: #8cc1f2; margin-bottom: 18px; }
.intro h2 { font-size: clamp(28px, 3.1vw, 42px); font-weight: 700; line-height: 1.3; margin-bottom: 28px; letter-spacing: -.5px; }
.intro ul { list-style: none; margin: 0; padding: 0; }
.intro li { display: flex; gap: 32px; padding: 9.5px 0; border-top: 1px solid rgba(140, 193, 242, .28); font-size: 14px; }
.intro li b { color: #8cc1f2; }
.intro li span { color: #d6e4f3; }
.auth-card {
  position: relative; z-index: 1; background: #fff; max-width: 400px; border-radius: 14px; padding: 32px 32px 28px;
  box-shadow: 0 24px 60px rgba(2, 8, 23, .5);
}
.auth-card.wide { max-width: 560px; }
.logo { font-size: 12px; font-weight: 700; letter-spacing: 2px; color: var(--pri); }
h1 { font-size: 22px; color: var(--navy); margin: 6px 0 4px; }
.sub { color: var(--muted); margin-bottom: 18px; }
form { display: flex; flex-direction: column; gap: 11px; }
.field input { height: 38px; padding: 4px 10px; border-radius: 6px; }
.field input.otp { height: 46px; font-size: 22px; text-align: center; letter-spacing: 8px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 11px 12px; }
.auth-err { min-height: 18px; margin: -8px 0 4px; color: var(--err); font-size: 12px; line-height: 18px; }
.submit { width: 100%; height: 42px; font-weight: 700; }
.foot { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--muted); margin-top: 1px; white-space: nowrap; }
.foot a { color: var(--pri); }
.foot a:only-child { text-decoration: underline; }
.foot a:not(:only-child) { text-decoration: none; }
@media (max-width: 1000px) {
  .auth { grid-template-columns: minmax(0, 1fr); justify-items: center; padding: 40px 16px; }
  .auth::after { content: ''; position: absolute; inset: 0; background: rgba(6, 15, 34, .4); pointer-events: none; }
  .intro { display: none; }
}
</style>
