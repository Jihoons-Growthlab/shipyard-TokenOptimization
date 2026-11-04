const MAX_BYTES = 30 * 1024 * 1024

export function pdfError(file) {
  if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') return 'PDF 파일만 업로드할 수 있습니다.'
  if (file.size > MAX_BYTES) return '파일 크기는 30MB 이하여야 합니다.'
  return null
}
