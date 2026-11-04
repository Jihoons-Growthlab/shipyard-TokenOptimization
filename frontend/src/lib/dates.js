// YYYY-MM-DD 문자열 날짜 계산. 시간대 영향을 피하려고 UTC로 계산한다.
const DAY_MS = 86400000

const toUtc = (text) => {
  const [year, month, day] = text.split('-').map(Number)
  return Date.UTC(year, month - 1, day)
}

export const diffDays = (from, to) => Math.round((toUtc(to) - toUtc(from)) / DAY_MS)
export const addDays = (text, days) => new Date(toUtc(text) + days * DAY_MS).toISOString().slice(0, 10)
export const monthStart = (text) => `${text.slice(0, 7)}-01`

export function nextMonth(text) {
  const [year, month] = text.split('-').map(Number)
  return new Date(Date.UTC(year, month, 1)).toISOString().slice(0, 10)
}
