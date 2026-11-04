// Unity 뷰어 수명주기. 인스턴스는 동시에 하나이며 새 시작은 이전 종료를 기다린다.
const BASE = '/unity/ship-viewer/Build/'
const READY_EVENT = 'shipviewer-ready'
export const READY_TIMEOUT_MS = 20000

let loader = null
let current = null

const firstLine = (error) => String(error?.message ?? error ?? '').split('\n')[0]

async function fetchManifest() {
  let response
  try {
    response = await fetch(`${BASE}build.json`, { cache: 'no-store' })
  } catch {
    throw new Error('3D 뷰어 빌드를 찾을 수 없습니다.')
  }
  try {
    if (!response.ok) throw new Error('not found')
    return JSON.parse(await response.text())
  } catch {
    // Vite SPA 폴백은 200 + HTML을 돌려준다
    throw new Error('3D 뷰어 빌드를 찾을 수 없습니다.')
  }
}

function loadScript(url) {
  if (window.createUnityInstance) return Promise.resolve()
  if (!loader) {
    loader = new Promise((resolve, reject) => {
      const tag = document.createElement('script')
      tag.src = url
      tag.onload = resolve
      tag.onerror = () => {
        tag.remove()
        loader = null
        reject(new Error('3D 뷰어 로더를 불러오지 못했습니다.'))
      }
      document.body.appendChild(tag)
    })
  }
  return loader
}

function releaseContext(canvas) {
  const context = canvas.getContext?.('webgl2') ?? canvas.getContext?.('webgl')
  context?.getExtension('WEBGL_lose_context')?.loseContext()
}

export function startViewer(canvas, { onProgress = () => {}, timeoutMs = READY_TIMEOUT_MS } = {}) {
  let cancelled = false
  let instance = null
  let timer = null
  let failLoad = () => {}
  let readyListener = null
  let abortWait = () => {}
  const aborted = new Promise((resolve) => { abortWait = resolve })

  const quit = async (target) => {
    try {
      await target.Quit()
    } catch {
      // 종료 실패는 다음 시작을 막지 않는다
    }
    releaseContext(canvas)
  }

  async function boot(waitFor) {
    await waitFor
    if (cancelled) return
    const manifest = await fetchManifest()
    if (cancelled) return
    await loadScript(BASE + manifest.loaderUrl)
    if (cancelled) return

    const ready = new Promise((resolve) => {
      readyListener = resolve
      canvas.addEventListener(READY_EVENT, resolve, { once: true })
    })
    const failure = new Promise((_, reject) => { failLoad = reject })
    const creating = window.createUnityInstance(canvas, {
      dataUrl: BASE + manifest.dataUrl,
      frameworkUrl: BASE + manifest.frameworkUrl,
      codeUrl: BASE + manifest.codeUrl,
      companyName: manifest.companyName,
      productName: manifest.productName,
      productVersion: manifest.productVersion,
      devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      showBanner: (message, type) => { if (type === 'error') failLoad(new Error(message)) },
    }, onProgress)

    let abandoned = false
    creating.then((created) => {
      if (abandoned) quit(created)
      else instance = created
    }, () => {})
    try {
      await Promise.race([creating, failure])
    } catch (error) {
      abandoned = true
      throw error
    }
    if (cancelled) return

    await Promise.race([
      ready,
      failure,
      aborted,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('3D 뷰어가 응답하지 않습니다.')), timeoutMs)
      }),
    ])
  }

  const prior = current
  const started = boot(prior ? prior.stop() : Promise.resolve())
  const whenReady = started.then(() => {
    if (cancelled) throw new Error('cancelled')
    return instance
  }).catch((error) => { throw new Error(firstLine(error)) })
  whenReady.catch(() => {})

  async function shutdown() {
    await started.catch(() => {})
    clearTimeout(timer)
    if (readyListener) canvas.removeEventListener(READY_EVENT, readyListener)
    if (instance) await quit(instance)
    instance = null
  }

  let stopped = null
  const stop = () => {
    if (!stopped) {
      cancelled = true
      abortWait()
      stopped = shutdown()
    }
    return stopped
  }

  current = {
    ready: whenReady,
    stop,
    setView: (view) => instance?.SendMessage('ShipViewer', 'SetView', view),
  }
  return current
}

export function resetViewerForTest() {
  loader = null
  current = null
}
