<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { startViewer } from '../../lib/unityViewer'

const VIEWS = [['front', '정면'], ['side', '측면'], ['top', '상단'], ['reset', '초기화']]
const HELP = [['왼쪽 드래그', '회전'], ['휠', '확대·축소'], ['오른쪽 드래그', '화면 이동']]

const canvas = ref(null)
const canvasKey = ref(0)
const progress = ref(0)
const state = ref('loading')
const reason = ref('')
let viewer = null

function start() {
  state.value = 'loading'
  progress.value = 0
  const session = startViewer(canvas.value, { onProgress: (value) => { progress.value = value } })
  viewer = session
  session.ready.then(
    () => { if (viewer === session) state.value = 'ready' },
    (error) => {
      if (viewer !== session) return
      reason.value = error.message
      state.value = 'failed'
      session.stop()
    },
  )
}

async function retry() {
  canvasKey.value += 1
  await nextTick()
  start()
}

onMounted(start)
onBeforeUnmount(() => {
  const session = viewer
  viewer = null
  session?.stop()
})
</script>

<template>
  <div class="viewer-tab">
    <div class="stage">
      <canvas :id="`ship-viewer-${canvasKey}`" :key="canvasKey" ref="canvas" tabindex="-1" @contextmenu.prevent />
      <div v-if="state === 'loading'" class="cover">
        <p>3D 뷰어 불러오는 중…</p>
        <div class="load"><i :style="{ width: `${Math.round(progress * 100)}%` }" /></div>
      </div>
      <div v-else-if="state === 'failed'" class="cover">
        <p><b>3D 뷰어를 불러오지 못했습니다.</b></p>
        <p class="why">{{ reason }}</p>
        <button class="btn" @click="retry">재시도</button>
      </div>
    </div>
    <aside class="info">
      <section class="card">
        <h3>샘플 호선 3D 뷰어</h3>
        <p class="name">Demo Ship 01</p>
        <div class="note warn">예시 모델 — 실제 호선 형상과 다름</div>
      </section>
      <section class="card">
        <h3>시점</h3>
        <div class="views">
          <button v-for="[view, label] in VIEWS" :key="view" class="btn" :disabled="state !== 'ready'" @click="viewer.setView(view)">{{ label }}</button>
        </div>
      </section>
      <section class="card">
        <h3>조작 안내</h3>
        <dl><template v-for="[key, text] in HELP" :key="key"><dt>{{ key }}</dt><dd>{{ text }}</dd></template></dl>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.viewer-tab { flex: 1 1 0 !important; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 12px; }
.stage { position: relative; min-height: 0; border: 1px solid var(--line); border-radius: 8px; background: #dde4ee; overflow: hidden; }
canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; outline: 0; }
.cover { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; background: #dde4ee; }
.why { color: var(--muted); font-size: 12px; }
.load { width: 240px; height: 8px; border-radius: 4px; background: #c5cedb; overflow: hidden; }
.load i { display: block; height: 100%; background: var(--pri); }
.info { overflow-y: auto; }
.name { font-size: 15px; font-weight: 700; margin-bottom: 10px; }
.note { margin: 0; }
.views { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
dl { display: grid; grid-template-columns: 95px 1fr; gap: 8px 0; margin: 0; font-size: 12px; }
dd { margin: 0; }
@media (max-width: 760px) {
  .viewer-tab { grid-template-columns: minmax(0, 1fr); flex: none !important; }
  .stage { min-height: 260px; }
  .info { max-height: 40vh; }
}
</style>
