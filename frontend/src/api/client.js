// 단일 HTTP 클라이언트. 모든 API 호출은 여기를 지난다.
export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || '요청을 처리하지 못했습니다.')
    this.status = status
    this.code = body?.code
    this.details = body?.details || {}
  }
}

let tokenProvider = () => null
let onUnauthorized = () => {}

export function configureClient({ getToken, unauthorized }) {
  tokenProvider = getToken
  onUnauthorized = unauthorized
}

function buildUrl(path, query) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, value)
  }
  const text = params.toString()
  return `/api${path}${text ? `?${text}` : ''}`
}

export async function request(method, path, { body, query, form, token, signal, raw } = {}) {
  const bearer = token ?? tokenProvider()
  const headers = {}
  if (bearer) headers.Authorization = `Bearer ${bearer}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetch(buildUrl(path, query), {
      method, headers, signal,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(0, { message: '서버에 연결할 수 없습니다.' })
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (response.status === 401 && bearer && !token) onUnauthorized()
    throw new ApiError(response.status, data)
  }
  if (raw) return response
  if (response.status === 204) return null
  return response.json()
}

export const api = {
  get: (path, options) => request('GET', path, options),
  post: (path, body, options) => request('POST', path, { ...options, body }),
  put: (path, body, options) => request('PUT', path, { ...options, body }),
  patch: (path, body, options) => request('PATCH', path, { ...options, body }),
  del: (path, options) => request('DELETE', path, options),
  upload: (path, form, options) => request('POST', path, { ...options, form }),
}
