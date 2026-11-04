import { reactive } from 'vue'

export const toasts = reactive([])
let seq = 0

export function toast(message, type = '') {
  const id = ++seq
  toasts.push({ id, message, type })
  setTimeout(() => {
    const index = toasts.findIndex((item) => item.id === id)
    if (index >= 0) toasts.splice(index, 1)
  }, 3500)
}

export const toastError = (error) => toast(error.message, 'error')
export const toastOk = (message) => toast(message, 'success')
