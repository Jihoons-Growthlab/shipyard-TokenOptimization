// 간트 레이아웃 계산. 화면과 분리해 테스트한다.
import { addDays, diffDays, monthStart, nextMonth } from './dates'

export const ROW_H = 28
export const HEAD_H = 34
export const LEFT_W = 230
const ELBOW = 4

export function ganttLayout(plans, deps, today, zoom) {
  const starts = plans.map((plan) => plan.plan_start_dt)
  const ends = plans.map((plan) => plan.plan_end_dt)
  const first = [addDays(today, -5), ...starts].sort()[0]
  const start = monthStart(first)
  const end = [addDays(today, 5), ...ends].sort().at(-1)
  const totalDays = diffDays(start, end) + 8
  const chartWidth = Math.ceil(totalDays * zoom)
  const xOf = (date) => diffDays(start, date) * zoom

  const months = []
  for (let cursor = start; diffDays(start, cursor) < totalDays; cursor = nextMonth(cursor)) {
    months.push({ key: cursor, x: xOf(cursor), label: cursor.slice(0, 7).replace('-', '.') })
  }

  const rowOf = new Map(plans.map((plan, index) => [plan.plan_id, index]))
  const bars = plans.map((plan, index) => ({
    plan,
    top: index * ROW_H + 6,
    x: xOf(plan.plan_start_dt),
    width: (diffDays(plan.plan_start_dt, plan.plan_end_dt) + 1) * zoom,
  }))

  const links = deps
    .filter((dep) => rowOf.has(dep.plan_id) && rowOf.has(dep.pred_plan_id))
    .map((dep) => {
      const pred = plans[rowOf.get(dep.pred_plan_id)]
      const succ = plans[rowOf.get(dep.plan_id)]
      const x0 = xOf(addDays(pred.plan_end_dt, 1))
      const y0 = rowOf.get(dep.pred_plan_id) * ROW_H + ROW_H / 2
      const y1 = rowOf.get(dep.plan_id) * ROW_H + ROW_H / 2
      return { key: `${dep.pred_plan_id}-${dep.plan_id}`, d: `M${x0} ${y0}H${x0 + ELBOW}V${y1}H${xOf(succ.plan_start_dt)}` }
    })

  return {
    months, bars, links, chartWidth,
    width: LEFT_W + chartWidth,
    height: HEAD_H + plans.length * ROW_H,
    todayX: xOf(today),
  }
}

export const initialScroll = (todayX, clientWidth) => Math.max(0, LEFT_W + todayX - clientWidth * 0.4)
