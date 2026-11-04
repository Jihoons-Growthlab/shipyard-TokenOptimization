<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { codeName } from '../../stores/session'
import { navigate } from '../../stores/shell'
import { toastError } from '../../stores/toast'

const props = defineProps({ hullNo: { type: String, required: true } })
const summary = ref(null)

onMounted(async () => {
  try {
    summary.value = await api.get(`/hulls/${props.hullNo}/summary`)
  } catch (error) {
    toastError(error)
  }
})

const entries = (group, counts) => Object.entries(counts).map(([code, count]) => ({ code, name: codeName(group, code), count }))
const plans = computed(() => entries('PLANSTAT', summary.value.plan_status))
const drawings = computed(() => entries('DWGSTAT', summary.value.drawing_status))
</script>

<template>
  <div v-if="summary" class="two">
    <div class="card">
      <h3 class="head">공정 <button class="btn sm" @click="navigate('plan-gantt', hullNo)">간트 보기</button></h3>
      <template v-if="summary.plan_count">
        <p>전체 진척 {{ summary.progress }}%</p>
        <ul><li v-for="item in plans" :key="item.code">{{ item.name }}: {{ item.count }}</li></ul>
      </template>
      <p v-else class="muted">공정 계획이 없습니다.</p>
    </div>
    <div class="card">
      <h3 class="head">도면 <button class="btn sm" @click="navigate('dwg-list', hullNo)">목록 보기</button></h3>
      <ul v-if="summary.drawing_count"><li v-for="item in drawings" :key="item.code">{{ item.name }}: {{ item.count }}</li></ul>
      <p v-else class="muted">도면이 없습니다.</p>
    </div>
  </div>
</template>

<style scoped>
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.card { margin: 0; min-height: 206px; }
.card > h3.head { display: flex; justify-content: flex-start; gap: 4px; margin: 16px 0 14px; }
ul { margin: 14px 0 0; }
.card > h3.head + ul { margin-top: 0; }
</style>
