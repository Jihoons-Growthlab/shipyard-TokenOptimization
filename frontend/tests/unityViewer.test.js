import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetViewerForTest, startViewer } from '../src/lib/unityViewer'

const MANIFEST = { loaderUrl: 'a.loader.js', dataUrl: 'a.data', frameworkUrl: 'a.framework.js', codeUrl: 'a.wasm', companyName: 'SWP', productName: 'P', productVersion: '1' }

const json = (value) => ({ ok: true, text: async () => JSON.stringify(value) })
const deferred = () => {
  const result = {}
  result.promise = new Promise((resolve, reject) => Object.assign(result, { resolve, reject }))
  return result
}
const instance = () => ({ Quit: vi.fn(async () => {}), SendMessage: vi.fn() })
function canvas() {
  const element = document.createElement('canvas')
  const lose = vi.fn()
  element.getContext = () => ({ getExtension: () => ({ loseContext: lose }) })
  element.lose = lose
  return element
}
const ready = (element) => element.dispatchEvent(new CustomEvent('shipviewer-ready'))

beforeEach(() => {
  resetViewerForTest()
  vi.stubGlobal('fetch', vi.fn(async () => json(MANIFEST)))
  window.createUnityInstance = vi.fn(async () => instance())
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  delete window.createUnityInstance
})

describe('unityViewer', () => {
  it('build.json이 HTML이면 빌드 없음 오류', async () => {
    fetch.mockResolvedValue({ ok: true, text: async () => '<!doctype html>' })
    await expect(startViewer(canvas()).ready).rejects.toThrow('3D 뷰어 빌드를 찾을 수 없습니다.')
  })

  it('준비는 인스턴스와 준비 신호가 모두 있어야 한다', async () => {
    const element = canvas()
    const session = startViewer(element)
    let done = false
    session.ready.then(() => { done = true })
    await flushPromises()
    expect(window.createUnityInstance).toHaveBeenCalledOnce()
    expect(done).toBe(false)
    ready(element)
    await flushPromises()
    expect(done).toBe(true)
    session.setView('top')
    const created = await window.createUnityInstance.mock.results[0].value
    expect(created.SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetView', 'top')
  })

  it('로더 실패 후 태그를 지워 재시도를 허용한다', async () => {
    delete window.createUnityInstance
    const session = startViewer(canvas())
    await flushPromises()
    const tag = document.querySelector('script[src*="a.loader.js"]')
    tag.onerror()
    await expect(session.ready).rejects.toThrow('로더')
    expect(document.querySelector('script[src*="a.loader.js"]')).toBeNull()
    const retry = startViewer(canvas())
    await flushPromises()
    await flushPromises()
    expect(document.querySelector('script[src*="a.loader.js"]')).not.toBeNull()
    document.querySelector('script[src*="a.loader.js"]').remove()
    window.createUnityInstance = vi.fn(async () => instance())
    retry.stop()
  })

  it('showBanner error는 실패, 오류는 첫 줄만', async () => {
    window.createUnityInstance = vi.fn((_, config) => {
      config.showBanner('wasm 실패\nstack', 'error')
      return new Promise(() => {})
    })
    await expect(startViewer(canvas()).ready).rejects.toThrow(/^wasm 실패$/)
  })

  it('준비 신호가 없으면 응답 없음 오류', async () => {
    vi.useFakeTimers()
    const session = startViewer(canvas(), { timeoutMs: 1000 })
    await vi.advanceTimersByTimeAsync(1100)
    await expect(session.ready).rejects.toThrow('3D 뷰어가 응답하지 않습니다.')
  })

  it('로딩 중 닫으면 늦게 온 인스턴스를 바로 종료하고 컨텍스트를 해제한다', async () => {
    const pending = deferred()
    window.createUnityInstance = vi.fn(() => pending.promise)
    const element = canvas()
    const session = startViewer(element)
    await flushPromises()
    session.stop()
    const late = instance()
    pending.resolve(late)
    await flushPromises()
    await flushPromises()
    expect(late.Quit).toHaveBeenCalledOnce()
    expect(element.lose).toHaveBeenCalledOnce()
  })

  it('새 시작은 이전 Quit 완료까지 기다린다', async () => {
    const quit = deferred()
    const first = instance()
    first.Quit = vi.fn(() => quit.promise)
    window.createUnityInstance = vi.fn(async () => first)
    const element = canvas()
    const session = startViewer(element)
    ready(element)
    await flushPromises()
    ready(element)
    await session.ready
    session.stop()
    startViewer(canvas())
    await flushPromises()
    expect(window.createUnityInstance).toHaveBeenCalledOnce()
    quit.resolve()
    await flushPromises()
    await flushPromises()
    expect(window.createUnityInstance).toHaveBeenCalledTimes(2)
  })
})
