<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import ScreenHead from '../../components/ScreenHead.vue'
import { useLatest } from '../../composables/useLatest'
import { codeName } from '../../stores/session'
import { navigate } from '../../stores/shell'
import { toastError } from '../../stores/toast'
import DrawingDetailModal from '../drawing/DrawingDetailModal.vue'
import { screenProps } from '../props'
import StatusDonut from './StatusDonut.vue'

const props = defineProps(screenProps)
const DRAWING_LEGEND = [['ISSUED', '배포', '#16a34a'], ['APPROVED', '승인', '#0ea5e9'], ['REVIEW', '검토중', '#f59e0b'], ['DRAFT', '작성중', '#94a3b8']]

const data = ref(null)
const drawingId = ref(null)
const latest = useLatest()

const kpis = computed(() => {
  const kpi = data.value.kpi
  return [
    { label: '진행 호선', ...kpi.active_hulls, tone: '' },
    { label: '지연 공정', ...kpi.delay_plans, tone: kpi.delay_plans.value ? 'err' : '' },
    { label: '도면 대기 공정', ...kpi.waiting_plans, tone: kpi.waiting_plans.value ? 'warn' : '' },
    { label: '결재·배포 대기 도면', ...kpi.pending_drawings, tone: kpi.pending_drawings.value ? 'warn' : '' },
  ]
})
const maxDelivery = computed(() => Math.max(1, ...data.value.deliveries.map((item) => item.count)))
const go = (link) => navigate(link.screen, link.param)

async function load() {
  const seq = latest.next()
  try {
    const result = await api.get('/dashboard/summary')
    if (latest.isCurrent(seq)) data.value = result
  } catch (error) {
    if (latest.isCurrent(seq)) toastError(error)
  }
}

onMounted(load)
watch(() => [props.tick, props.active], ([, active]) => { if (active) load() })
</script>

<template>
  <ScreenHead title="대시보드" :desc="`기준일 ${data?.today ?? ''} · 호선/공정/도면 현황`" :readonly="!canWrite" />
  <template v-if="data">
    <div class="kpis">
      <button v-for="kpi in kpis" :key="kpi.label" class="card kpi" @click="go(kpi.link)">
        <span>{{ kpi.label }}</span><b :class="kpi.tone">{{ kpi.value }}</b>
      </button>
    </div>
    <div class="grid">
      <section class="card">
        <h3>호선별 진척률</h3>
        <button v-for="hull in data.hull_progress" :key="hull.hull_no" class="hp" @click="go(hull.link)">
          <span class="nm">{{ hull.hull_no }} {{ hull.hull_nm }}</span>
          <span class="track"><i :style="{ width: `${hull.progress}%` }" /></span>
          <b>{{ hull.progress }}%</b>
        </button>
      </section>
      <section class="card">
        <h3>공정 상태 분포</h3>
        <StatusDonut :items="data.plan_status" />
      </section>
      <section class="card">
        <h3>분야별 도면 상태</h3>
        <div v-for="item in data.drawing_disciplines" :key="item.discipline" class="disc">
          <div class="dn">{{ item.name }} <span class="muted">({{ item.total }})</span></div>
          <div class="stack">
            <template v-for="[code, , color] in DRAWING_LEGEND" :key="code">
              <i v-if="item.counts[code]" :style="{ flex: item.counts[code], background: color }" :title="`${code} ${item.counts[code]}`" />
            </template>
          </div>
        </div>
        <div class="legend"><span v-for="[code, name, color] in DRAWING_LEGEND" :key="code"><i :style="{ background: color }" />{{ name }}</span></div>
      </section>
      <section class="card">
        <h3>월별 인도 예정</h3>
        <div class="months">
          <div v-for="item in data.deliveries" :key="item.month" class="mon">
            <span class="v">{{ item.count }}</span>
            <i :style="{ height: `${item.count / maxDelivery * 80}px` }" />
            <span class="m">{{ item.month.slice(2) }}</span>
            <span class="h">{{ item.hull_nos.join(',') }}</span>
          </div>
        </div>
      </section>
      <section class="card">
        <h3>지연 공정 <span class="bdg bad">{{ data.delay_list.count }}</span></h3>
        <button v-for="item in data.delay_list.items" :key="item.plan_id" class="line" @click="go(item.link)">
          <span>{{ item.hull_no }} {{ item.label }}</span>
          <small>{{ item.progress_rate }}% · 계획종료 {{ item.plan_end_dt }}</small>
        </button>
        <p v-if="!data.delay_list.count" class="muted none">지연 공정이 없습니다.</p>
      </section>
      <section class="card">
        <h3>도면 대기 공정 <span class="bdg warn">{{ data.waiting_list.count }}</span></h3>
        <button v-for="item in data.waiting_list.items" :key="item.plan_id" class="line" @click="go(item.link)">
          <span>{{ item.hull_no }} {{ item.label }}</span>
          <small>착수 {{ item.plan_start_dt }} · {{ item.blockers.join(', ') }}</small>
        </button>
        <p v-if="!data.waiting_list.count" class="muted none">대기 중인 공정이 없습니다.</p>
      </section>
      <section class="card wide">
        <h3>도면 개정 영향 공정 <span class="bdg info">{{ data.impact_list.count }}</span></h3>
        <button v-for="item in data.impact_list.items" :key="`${item.drawing_id}-${item.plan_id}`" class="line" @click="drawingId = item.drawing_id">
          <span>{{ item.drawing_no }} Rev{{ item.rev_no }} → {{ item.plan_label }} <em class="bdg" :class="item.plan_status">{{ codeName('PLANSTAT', item.plan_status) }}</em></span>
          <small>{{ item.change_desc }} · 배포 {{ item.issue_dt }}</small>
        </button>
        <p v-if="!data.impact_list.count" class="muted none">최근 개정된 도면의 영향 공정이 없습니다.</p>
      </section>
    </div>
  </template>
  <DrawingDetailModal v-if="drawingId" :drawing-id="drawingId" @changed="load" @close="drawingId = null" />
</template>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi { margin: 0; text-align: left; cursor: pointer; display: flex; flex-direction: column; gap: 2px; font: inherit; color: inherit; }
.kpi:hover { border-color: var(--pri); }
.kpi span { font-size: 12px; color: var(--muted); }
.kpi b { font-size: 26px; color: var(--navy); }
.kpi b.err { color: var(--err); }
.kpi b.warn { color: var(--warn); }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.grid .card { margin: 0; min-width: 0; }
.wide { grid-column: 1 / -1; }
.hp { display: grid; grid-template-columns: 130px 1fr 44px; gap: 8px; align-items: center; width: 100%; height: 23px; padding: 0; background: none; border: 0; cursor: pointer; text-align: left; font: inherit; color: inherit; font-size: 12px; }
.hp .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track { height: 14px; border-radius: 7px; background: #e5e7eb; overflow: hidden; display: block; }
.track i { display: block; height: 100%; background: var(--pri); }
.hp b { font-size: 13px; }
.disc { margin-bottom: 9px; }
.dn { font-size: 12px; margin-bottom: 4px; }
.stack { display: flex; height: 16px; border-radius: 3px; overflow: hidden; }
.legend { display: flex; gap: 14px; font-size: 12px; margin-top: 6px; }
.legend span { display: inline-flex; align-items: center; gap: 4px; }
.legend i { width: 10px; height: 10px; border-radius: 2px; }
.months { height: 130px; display: flex; align-items: flex-end; justify-content: space-around; gap: 8px; margin-top: 14px; }
.mon { display: flex; flex-direction: column; align-items: center; width: 44px; }
.mon i { display: block; width: 44px; background: var(--navy2); margin: 2px 0 3px; }
.v { font-size: 11px; font-weight: 700; }
.m, .h { font-size: 10px; color: var(--muted); white-space: nowrap; }
.h { color: var(--ink); }
.line { display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; min-height: 31px; padding: 4px 4px; background: none; border: 0; border-bottom: 1px solid var(--line2); cursor: pointer; text-align: left; font: inherit; color: inherit; }
.line:last-of-type { border-bottom: 0; }
.line:hover { background: var(--hover); }
.line small { font-size: 12px; color: var(--muted); white-space: nowrap; }
.line em { font-style: normal; }
.none { padding: 8px 4px; }
</style>
