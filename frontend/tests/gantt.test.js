import { describe, expect, it } from 'vitest'
import { diffDays } from '../src/lib/dates'
import { ganttLayout, initialScroll } from '../src/lib/gantt'

const plan = (id, start, end) => ({ plan_id: id, plan_start_dt: start, plan_end_dt: end })

describe('ganttLayout', () => {
  const plans = [plan(1, '2026-06-15', '2026-06-28'), plan(2, '2027-03-01', '2027-03-20')]
  const layout = ganttLayout(plans, [{ plan_id: 2, pred_plan_id: 1 }], '2026-10-19', 4)

  it('시작은 달의 1일, 폭은 230 + ceil(총 일수 × 배율)', () => {
    expect(layout.months[0].label).toBe('2026.06')
    const total = diffDays('2026-06-01', '2027-03-20') + 8
    expect(layout.width).toBe(230 + total * 4)
    expect(layout.height).toBe(34 + 28 * 2)
    expect(layout.todayX).toBe(diffDays('2026-06-01', '2026-10-19') * 4)
  })

  it('막대와 선후행선 좌표', () => {
    expect(layout.bars[0]).toMatchObject({ x: 14 * 4, width: 14 * 4, top: 6 })
    const x0 = 28 * 4
    expect(layout.links[0].d).toBe(`M${x0} 14H${x0 + 4}V42H${diffDays('2026-06-01', '2027-03-01') * 4}`)
  })

  it('오늘이 범위 밖이면 오늘±5일까지 포함', () => {
    const result = ganttLayout([plan(1, '2026-11-01', '2026-11-02')], [], '2026-10-01', 2.5)
    expect(result.months[0].label).toBe('2026.09')
  })

  it('처음 스크롤은 오늘선을 폭의 40% 위치에', () => {
    expect(initialScroll(1000, 1000)).toBe(830)
    expect(initialScroll(0, 1000)).toBe(0)
  })
})
