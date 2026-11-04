import { reactive } from 'vue'
import { api, configureClient } from '../api/client'

const KEY = 'swp_token'

function readToken() {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export const session = reactive({ token: readToken(), user: null, codes: null })

export function startSession(result) {
  session.token = result.access_token
  session.user = result.user
  sessionStorage.setItem(KEY, result.access_token)
}

export function clearSession() {
  session.token = null
  session.user = null
  session.codes = null
  sessionStorage.removeItem(KEY)
  sessionStorage.removeItem('swp_tabs')
}

export function configureSession(router) {
  configureClient({
    getToken: () => session.token,
    unauthorized: () => {
      clearSession()
      router.replace('/login')
    },
  })
}

export async function loadCodes() {
  if (!session.codes) session.codes = await api.get('/codes')
  return session.codes
}

export function codeName(group, code) {
  return session.codes?.[group]?.find((item) => item.code === code)?.name ?? code ?? ''
}
