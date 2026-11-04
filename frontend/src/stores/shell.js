// 메뉴·탭 상태와 화면 이동.
import { reactive } from 'vue'
import { api } from '../api/client'
import { session } from './session'
import { toast } from './toast'

const KEY = 'swp_tabs'
export const MAX_TABS = 12

export const shell = reactive({ menus: [], tabs: [], active: null, navTick: 0 })

const tabKey = (token, param) => `${token}:${param ?? ''}`
const menuOf = (token) => shell.menus.find((menu) => menu.token === token)

export const canWrite = (token) => Boolean(menuOf(token)?.can_write)
export const hasMenu = (token) => Boolean(menuOf(token))
export const activeTab = () => shell.tabs.find((tab) => tab.key === shell.active)

function persist() {
  const tabs = shell.tabs.map(({ token, param }) => ({ token, param }))
  sessionStorage.setItem(KEY, JSON.stringify({ tabs, active: shell.active }))
}

function makeTab(token, param) {
  const title = menuOf(token).title
  return { key: tabKey(token, param), token, param: param ?? null, title: param ? `${title} (${param})` : title, tick: 0 }
}

export function closeTab(key) {
  const index = shell.tabs.findIndex((tab) => tab.key === key)
  if (index < 0) return
  shell.tabs.splice(index, 1)
  if (shell.active === key) {
    shell.active = (shell.tabs[index] ?? shell.tabs[index - 1])?.key ?? null
  }
  persist()
}

export function closeOtherTabs() {
  shell.tabs = shell.tabs.filter((tab) => tab.key === shell.active)
  persist()
}

export function activateTab(key) {
  shell.active = key
  persist()
}

export async function openTab(token, param) {
  const key = tabKey(token, param)
  const existing = shell.tabs.find((tab) => tab.key === key)
  if (existing) {
    existing.tick += 1
    activateTab(key)
    return
  }
  if (shell.tabs.length >= MAX_TABS) {
    toast('탭은 최대 12개까지 열 수 있습니다. 사용하지 않는 탭을 닫아주세요.', 'error')
    return
  }
  shell.tabs.push(makeTab(token, param))
  activateTab(key)
  try {
    await api.post('/me/menu-access', { menu_id: menuOf(token).menu_id })
  } catch (error) {
    if (error.status === 403) {
      closeTab(key)
      toast(error.message, 'error')
    }
  }
}

export function navigate(token, param) {
  shell.navTick += 1
  if (!hasMenu(token)) {
    toast('해당 화면에 대한 권한이 없습니다.', 'error')
    return
  }
  return openTab(token, param == null ? undefined : String(param))
}

function readSaved() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY)) ?? {}
  } catch {
    return {}
  }
}

export function restoreTabs() {
  const saved = readSaved()
  shell.tabs = (saved.tabs ?? []).filter((tab) => hasMenu(tab.token)).map((tab) => makeTab(tab.token, tab.param))
  if (shell.tabs.length) {
    shell.active = shell.tabs.some((tab) => tab.key === saved.active) ? saved.active : shell.tabs[0].key
    persist()
    return
  }
  shell.active = null
  const first = menuOf('dashboard') ?? shell.menus.find((menu) => menu.token)
  if (first) return openTab(first.token)
}

// 진입 시와 본인 정보 변경 시 세션·메뉴를 다시 불러온다.
export async function refreshAccount() {
  const [user, menus] = await Promise.all([api.get('/auth/me'), api.get('/me/menu')])
  session.user = user
  shell.menus = menus
  await restoreTabs()
}
