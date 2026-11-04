import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import PlanGanttScreen from '../src/screens/plan/PlanGanttScreen.vue'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../src/api/client', async (original) => ({ ...(await original()), api: { get } }))

const plans = (hull) => ({ hull_no: hull, hull_progress: 0, today: '2026-10-19', plans: [], deps: [] })

describe('공정 계획 호선 전환', () => {
  it('첫 호선 응답이 끝난 뒤에도 마지막으로 고른 호선의 응답을 버리지 않는다', async () => {
    const waiting = {}
    get.mockImplementation((path) => {
      if (path === '/plan-hulls') return Promise.resolve([{ hull_no: '8001', hull_nm: 'A', plan_count: 1 }, { hull_no: '8004', hull_nm: 'B', plan_count: 0 }])
      if (path.endsWith('/plans')) return new Promise((resolve) => { waiting[path] = resolve })
      return Promise.resolve([])
    })
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
    const wrapper = mount(PlanGanttScreen, { props: { title: '공정 계획', canWrite: true } })
    await flushPromises()
    await wrapper.find('select').setValue('8004')
    await flushPromises()
    waiting['/hulls/8001/plans'](plans('8001'))
    await flushPromises()
    waiting['/hulls/8004/plans'](plans('8004'))
    await flushPromises()
    expect(wrapper.text()).toContain('표시할 공정이 없습니다.')
    wrapper.unmount()
    vi.unstubAllGlobals()
  })
})
