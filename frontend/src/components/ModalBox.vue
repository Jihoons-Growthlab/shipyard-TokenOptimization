<script setup>
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { shell } from '../stores/shell'

const props = defineProps({ title: { type: String, required: true }, size: { type: String, default: '' } })
const emit = defineEmits(['close'])

function onKey(event) {
  if (event.key === 'Escape' && stack.at(-1) === onKey) emit('close')
}

onMounted(() => {
  stack.push(onKey)
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  stack.splice(stack.indexOf(onKey), 1)
  window.removeEventListener('keydown', onKey)
})
watch(() => shell.navTick, () => emit('close'))
</script>

<script>
// 겹친 모달에서 Esc는 맨 위 모달만 닫는다.
const stack = []
</script>

<template>
  <Teleport to="body">
    <div class="modal-back" @mousedown.self="emit('close')">
      <div class="modal" :class="props.size" role="dialog" :aria-label="props.title">
        <header>
          <span class="modal-title">{{ props.title }}</span>
          <slot name="head" />
          <button class="close" @click="emit('close')">닫기 ✕</button>
        </header>
        <div class="modal-body"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-back { position: fixed; inset: 0; z-index: 1000; background: rgba(15, 23, 42, .55); display: flex; align-items: center; justify-content: center; }
.modal { background: var(--bg); border-radius: 10px; box-shadow: 0 24px 60px rgba(0, 0, 0, .35); max-height: 94vh; width: 760px; max-width: 96vw; display: flex; flex-direction: column; overflow: hidden; }
.modal.large { width: 1100px; }
.modal.xl { width: min(1640px, 97vw); max-width: none; height: 94vh; }
header { background: var(--navy); color: #fff; padding: 10px 16px; display: flex; align-items: center; gap: 10px; }
.modal-title { font-size: 14px; font-weight: 700; margin-right: auto; }
.close { background: none; border: 1px solid #3b5a8c; color: #fff; border-radius: 5px; height: 24px; padding: 0 7px; font-size: 12px; cursor: pointer; }
.modal-body { padding: 14px 18px 20px; overflow: auto; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.modal-body > :deep(*) { flex-shrink: 0; }
</style>
