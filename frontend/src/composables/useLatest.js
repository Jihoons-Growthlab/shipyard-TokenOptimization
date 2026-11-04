// 늦게 도착한 응답을 버리기 위한 요청 순번.
export function useLatest() {
  let seq = 0
  return {
    next: () => ++seq,
    isCurrent: (value) => value === seq,
  }
}
