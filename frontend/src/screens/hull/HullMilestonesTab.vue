<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import { toastError, toastOk } from '../../stores/toast'

const props = defineProps({ hullNo: { type: String, required: true }, canWrite: Boolean })
const items = ref([])
const url = `/hulls/${props.hullNo}/milestones`

onMounted(async () => {
  try {
    items.value = await api.get(url)
  } catch (error) {
    toastError(error)
  }
})

async function save() {
  try {
    const payload = items.value.map(({ milestone_cd, plan_dt, actual_dt }) => ({ milestone_cd, plan_dt, actual_dt }))
    items.value = await api.put(url, { items: payload })
    toastOk('주요일정이 저장되었습니다.')
  } catch (error) {
    toastError(error)
  }
}
</script>

<template>
  <div class="card">
    <div class="tw">
      <table class="t">
        <thead><tr><th class="c1">일정</th><th>계획일</th><th>실적일</th><th>차이(일)</th></tr></thead>
        <tbody>
          <tr v-for="item in items" :key="item.milestone_cd">
            <td>{{ item.name }}</td>
            <td><input v-model="item.plan_dt" class="input date" type="date" :disabled="!canWrite" /></td>
            <td><input v-model="item.actual_dt" class="input date" type="date" :disabled="!canWrite" /></td>
            <td class="num">{{ item.diff_days ?? '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <button class="btn pri save" :disabled="!canWrite" @click="save">일정 저장</button>
  </div>
</template>

<style scoped>
.c1 { width: 25%; }
.input.date { width: auto; }
.save { margin-top: 12px; }
</style>
