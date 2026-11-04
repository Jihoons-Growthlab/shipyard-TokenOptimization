import { api } from '../../api/client'

export const pdfUrl = (drawingId, revNo) => `/drawings/${drawingId}/revisions/${revNo}/pdf`

export const uploadPdf = (drawingId, revNo, file) =>
  api.upload(pdfUrl(drawingId, revNo), file, { query: { filename: file.name } })

export const issueRevision = (drawingId, revNo) => api.post(`/drawings/${drawingId}/revisions/${revNo}/issue`)

export const STEP_NAMES = { 1: '검토', 2: '승인' }
export const RESULT_BADGES = { WAIT: ['warn', '대기'], APPROVE: ['ok', '승인'], REJECT: ['bad', '반려'] }
