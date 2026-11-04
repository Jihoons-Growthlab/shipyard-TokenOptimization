<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import CodeSelect from '../../components/CodeSelect.vue'
import ProgressBar from '../../components/ProgressBar.vue'
import { codeName } from '../../stores/session'
import { toastError, toastOk } from '../../stores/toast'

const props = defineProps({ hullNo: { type: String, required: true }, canWrite: Boolean })
const emit = defineEmits(['changed'])

const blank = () => ({ block_cd: '', block_nm: '', block_type: '', weight_ton: '' })
const blocks = ref([])
const form = ref(blank())
const url = `/hulls/${props.hullNo}/blocks`

async function load() {
  try {
    blocks.value = await api.get(url)
  } catch (error) {
    toastError(error)
  }
}

async function add() {
  try {
    const { weight_ton: weight } = form.value
    await api.post(url, { ...form.value, weight_ton: weight === '' ? null : Number(weight) })
    form.value = blank()
    toastOk('블록이 추가되었습니다.')
    await load()
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

async function remove(block) {
  if (!window.confirm('블록과 해당 블록의 공정을 삭제합니다. (도면의 블록 연결은 해제)')) return
  try {
    await api.del(`/blocks/${block.block_id}`)
    toastOk('삭제되었습니다.')
    await load()
    emit('changed')
  } catch (error) {
    toastError(error)
  }
}

onMounted(load)
</script>

<template>
  <div class="card">
    <div class="tw">
      <table class="t">
        <thead>
          <tr>
            <th>블록코드</th><th>블록명</th><th>유형</th><th>중량(ton)</th><th>진척</th>
            <th>공정</th><th>도면</th><th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="block in blocks" :key="block.block_id">
            <td><b>{{ block.block_cd }}</b></td>
            <td>{{ block.block_nm }}</td>
            <td>{{ codeName('BLOCKTYPE', block.block_type) }}</td>
            <td class="num">{{ block.weight_ton }}</td>
            <td class="prog"><ProgressBar v-if="block.progress !== null" :value="block.progress" /><template v-else>-</template></td>
            <td class="num">{{ block.plan_count }}</td>
            <td class="num">{{ block.drawing_count }}</td>
            <td><button class="btn sm danger" :disabled="!canWrite" @click="remove(block)">삭제</button></td>
          </tr>
          <tr v-if="!blocks.length"><td colspan="8" class="empty">블록이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <form class="filters add" @submit.prevent="add">
      <input v-model="form.block_cd" class="input" placeholder="블록코드 *" :disabled="!canWrite" />
      <input v-model="form.block_nm" class="input" placeholder="블록명" :disabled="!canWrite" />
      <CodeSelect v-model="form.block_type" class="input" group="BLOCKTYPE" empty="유형 선택" :disabled="!canWrite" />
      <input v-model="form.weight_ton" class="input" type="number" step="any" placeholder="중량(ton)" :disabled="!canWrite" />
      <button class="btn pri" :disabled="!canWrite">+ 블록 추가</button>
    </form>
  </div>
</template>

<style scoped>
.prog { width: 220px; }
.add { margin: 12px 0 0; }
</style>
