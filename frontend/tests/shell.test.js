import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { ApiError } from '../src/api/client'
import ModalBox from '../src/components/ModalBox.vue'
import WeatherPill from '../src/components/WeatherPill.vue'
import { closeTab, MAX_TABS, navigate, openTab, restoreTabs, shell } from '../src/stores/shell'
import { toasts } from '../src/stores/toast'

const { post, get } = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }))
vi.mock('../src/api/client', async (original) => ({
  ...(await original()),
  api: { post, get },
}))

const menu = (token, id, canWrite = false) => ({ menu_id: id, token, title: token, can_write: canWrite })

beforeEach(() => {
  post.mockReset().mockResolvedValue(null)
  get.mockReset()
  sessionStorage.clear()
  toasts.splice(0)
  shell.tabs = []
  shell.active = null
  shell.menus = [menu('dashboard', 'M00'), menu('hull-list', 'M11'), menu('plan-gantt', 'M21')]
})

describe('tabs', () => {
  it('T02 같은 화면은 탭 하나', async () => {
    await openTab('hull-list')
    await openTab('hull-list')
    expect(shell.tabs).toHaveLength(1)
    expect(shell.tabs[0].tick).toBe(1)
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('T03 13번째 탭 오류, 기존 탭 유지', async () => {
    for (let i = 0; i < MAX_TABS; i += 1) await openTab('plan-gantt', String(i))
    await openTab('hull-list')
    expect(shell.tabs).toHaveLength(MAX_TABS)
    expect(toasts[0].message).toContain('최대 12개')
  })

  it('닫으면 같은 위치의 다음 탭 활성', async () => {
    await openTab('dashboard')
    await openTab('hull-list')
    await openTab('plan-gantt')
    shell.active = 'hull-list:'
    closeTab('hull-list:')
    expect(shell.active).toBe('plan-gantt:')
  })

  it('menu-access 403이면 탭을 닫고 토스트', async () => {
    post.mockRejectedValue(new ApiError(403, { message: '접근 권한이 없습니다.' }))
    await openTab('hull-list')
    expect(shell.tabs).toHaveLength(0)
    expect(toasts[0].message).toBe('접근 권한이 없습니다.')
  })

  it('T05 복구 시 권한 없는 탭 제외', async () => {
    sessionStorage.setItem('swp_tabs', JSON.stringify({
      tabs: [{ token: 'user-mgmt', param: null }, { token: 'hull-list', param: null }], active: 'user-mgmt:',
    }))
    await restoreTabs()
    expect(shell.tabs.map((tab) => tab.token)).toEqual(['hull-list'])
    expect(shell.active).toBe('hull-list:')
  })

  it('복구할 탭이 없으면 대시보드', async () => {
    sessionStorage.setItem('swp_tabs', JSON.stringify({ tabs: [{ token: 'user-mgmt', param: null }], active: null }))
    await restoreTabs()
    expect(shell.active).toBe('dashboard:')
  })

  it('권한 없는 화면 이동 거절', async () => {
    await navigate('user-mgmt')
    expect(toasts[0].message).toBe('해당 화면에 대한 권한이 없습니다.')
  })
})

describe('modal', () => {
  it('T04 Esc·닫기·이동 시 닫힘, 겹치면 위만 닫힘', async () => {
    const under = mount(ModalBox, { props: { title: 'a' }, global: { stubs: { Teleport: true } } })
    const top = mount(ModalBox, { props: { title: 'b' }, global: { stubs: { Teleport: true } } })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(top.emitted('close')).toHaveLength(1)
    expect(under.emitted('close')).toBeUndefined()
    top.unmount()
    await under.find('.close').trigger('click')
    expect(under.emitted('close')).toHaveLength(1)
    await navigate('hull-list')
    await nextTick()
    expect(under.emitted('close')).toHaveLength(2)
    under.unmount()
  })
})

describe('weather', () => {
  const sample = (region) => ({ region, source: 'SAMPLE', tempC: 17.6, condition: '맑음', humidity: 52, windMs: 3.2 })

  it('T01 지역별 요청, T03 늦은 응답 무시', async () => {
    const pending = {}
    get.mockImplementation((_, { query }) => new Promise((resolve) => { pending[query.region] = resolve }))
    const wrapper = mount(WeatherPill)
    expect(wrapper.text()).toContain('날씨 조회 중…')
    await wrapper.find('select').setValue('거제')
    pending['거제'](sample('거제'))
    await flushPromises()
    pending['울산']({ ...sample('울산'), tempC: 1 })
    await flushPromises()
    expect(wrapper.text()).toContain('17.6℃')
    expect(localStorage.getItem('swp_region')).toBe('거제')
    wrapper.unmount()
  })

  it('T02 샘플은 LIVE로 표시하지 않고 실패 문구 표시', async () => {
    get.mockResolvedValueOnce(sample('울산'))
    const wrapper = mount(WeatherPill)
    await flushPromises()
    expect(wrapper.text()).toContain('샘플')
    expect(wrapper.text()).not.toContain('LIVE')
    wrapper.unmount()
    get.mockRejectedValueOnce(new Error('x'))
    const failed = mount(WeatherPill)
    await flushPromises()
    expect(failed.text()).toContain('날씨 조회 실패')
    failed.unmount()
  })
})
