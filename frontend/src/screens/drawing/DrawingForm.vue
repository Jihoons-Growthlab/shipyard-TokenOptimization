<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../../api/client'
import CodeSelect from '../../components/CodeSelect.vue'
import { toastError } from '../../stores/toast'

const props = defineProps({
  form: { type: Object, required: true },
  isNew: Boolean,
  disabled: Boolean,
})

const hulls = ref([])
const users = ref([])
const blocks = ref([])

async function loadBlocks() {
  if (!props.form.hull_no) return
  try {
    blocks.value = await api.get(`/hulls/${props.form.hull_no}/blocks`)
  } catch (error) {
    toastError(error)
  }
}

onMounted(async () => {
  try {
    const [hullList, options] = await Promise.all([api.get('/hulls'), api.get('/users/options')])
    hulls.value = hullList
    users.value = options
    if (!props.form.hull_no) props.form.hull_no = hullList[0]?.hull_no ?? ''
    await loadBlocks()
  } catch (error) {
    toastError(error)
  }
})

function changeHull() {
  props.form.block_id = ''
  loadBlocks()
}

watch(() => props.form.hull_no, (next, previous) => { if (previous === '' && next) loadBlocks() })
</script>

<template>
  <div class="fg c2">
    <div class="field"><label>도면번호 *</label><input v-model="form.drawing_no" :readonly="!isNew" :disabled="disabled" /></div>
    <div class="field"><label>분야</label><CodeSelect v-model="form.discipline" group="DWGDISC" :disabled="disabled" /></div>
    <div class="field span2"><label>도면명 *</label><input v-model="form.drawing_nm" :disabled="disabled" /></div>
    <div class="field"><label>호선</label>
      <select v-model="form.hull_no" :disabled="!isNew" @change="changeHull">
        <option v-for="hull in hulls" :key="hull.hull_no" :value="hull.hull_no">{{ hull.hull_no }} {{ hull.hull_nm }}</option>
      </select>
    </div>
    <div class="field"><label>블록</label>
      <select v-model="form.block_id" :disabled="disabled">
        <option value="">블록 없음</option>
        <option v-for="block in blocks" :key="block.block_id" :value="block.block_id">{{ block.block_cd }} {{ block.block_nm }}</option>
      </select>
    </div>
    <div class="field span2"><label>설계자</label>
      <select v-model="form.designer_emp_no" :disabled="disabled">
        <option value="">-</option>
        <option v-for="user in users" :key="user.emp_no" :value="user.emp_no">{{ user.display_name }} ({{ user.emp_no }})</option>
      </select>
    </div>
    <slot />
  </div>
</template>
