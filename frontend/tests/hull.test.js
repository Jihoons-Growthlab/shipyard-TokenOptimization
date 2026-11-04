import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import HullInfoTab from '../src/screens/hull/HullInfoTab.vue'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../src/api/client', async (original) => ({ ...(await original()), api: { get } }))

describe('호선 기본정보', () => {
  it('조회 완료 전 폼 비활성화로 늦은 응답의 덮어쓰기를 막는다', async () => {
    let resolve
    get.mockReturnValue(new Promise((r) => { resolve = r }))
    const wrapper = mount(HullInfoTab, { props: { hullNo: '8001', canWrite: true } })
    expect(wrapper.find('button.pri').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('input').every((input) => input.attributes('disabled') !== undefined)).toBe(true)
    resolve({ hull_no: '8001', hull_nm: 'A', hull_status: 'BUILD', use_yn: true })
    await flushPromises()
    expect(wrapper.find('button.pri').attributes('disabled')).toBeUndefined()
  })

  it('조회 전용은 저장·삭제 비활성', async () => {
    get.mockResolvedValue({ hull_no: '8001', hull_nm: 'A', hull_status: 'BUILD', use_yn: true })
    const wrapper = mount(HullInfoTab, { props: { hullNo: '8001', canWrite: false } })
    await flushPromises()
    expect(wrapper.find('button.pri').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button.danger').attributes('disabled')).toBeDefined()
  })
})
