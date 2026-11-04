<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import WeatherPill from '../components/WeatherPill.vue'
import { SCREENS } from '../screens'
import { clearSession, loadCodes, session } from '../stores/session'
import { activateTab, activeTab, canWrite, closeOtherTabs, closeTab, navigate, refreshAccount, shell } from '../stores/shell'

const router = useRouter()
const ready = ref(false)
const collapsed = reactive({})

const roots = computed(() => shell.menus.filter((menu) => !menu.parent_id))
const childrenOf = (id) => shell.menus.filter((menu) => menu.parent_id === id)
const activeToken = computed(() => activeTab()?.token)
const groupNames = computed(() => session.user?.groups.map((group) => group.name).join(', '))

onMounted(async () => {
  try {
    await Promise.all([refreshAccount(), loadCodes()])
    ready.value = true
  } catch (error) {
    if (error.status !== 401) router.replace('/login')
  }
})

async function logout() {
  try {
    await api.post('/auth/logout')
  } catch {
    // API 실패와 무관하게 세션을 지운다
  }
  clearSession()
  shell.tabs = []
  shell.active = null
  router.replace('/login')
}
</script>

<template>
  <div v-if="ready" class="shell">
    <header class="top">
      <div class="brand">⚓ SWP 조선소 통합관리</div>
      <div class="tag">호선 / 공정 / 도면</div>
      <div class="spacer" />
      <WeatherPill />
      <div class="who">
        <b>{{ session.user.display_name }} 님</b>
        <small>{{ groupNames }} · {{ session.user.today }}</small>
      </div>
      <button class="out" @click="logout">로그아웃</button>
    </header>
    <div class="body">
      <nav class="menu">
        <div class="menu-label">MENU</div>
        <template v-for="root in roots" :key="root.menu_id">
          <button
            v-if="root.token" class="item" :class="{ on: activeToken === root.token }"
            @click="navigate(root.token)"
          ><i>·</i>{{ root.title }}</button>
          <template v-else>
            <button class="item" @click="collapsed[root.menu_id] = !collapsed[root.menu_id]">
              <i class="arrow">{{ collapsed[root.menu_id] ? '▶' : '▼' }}</i>{{ root.title }}
            </button>
            <template v-if="!collapsed[root.menu_id]">
              <button
                v-for="child in childrenOf(root.menu_id)" :key="child.menu_id" class="item sub"
                :class="{ on: activeToken === child.token }" @click="navigate(child.token)"
              ><i>·</i>{{ child.title }}</button>
            </template>
          </template>
        </template>
      </nav>
      <main class="main">
        <div class="tabs">
          <div
            v-for="tab in shell.tabs" :key="tab.key" class="tab" :class="{ on: tab.key === shell.active }"
            @click="activateTab(tab.key)"
          >
            <span>{{ tab.title }}</span>
            <button class="x" aria-label="탭 닫기" @click.stop="closeTab(tab.key)">×</button>
          </div>
          <button v-if="shell.tabs.length >= 2" class="btn sm others" @click="closeOtherTabs">다른 탭 닫기</button>
        </div>
        <template v-for="tab in shell.tabs" :key="tab.key">
          <section v-show="tab.key === shell.active" class="work">
            <component
              :is="SCREENS[tab.token]" :title="tab.title" :param="tab.param" :tick="tab.tick"
              :can-write="canWrite(tab.token)" :active="tab.key === shell.active"
            />
          </section>
        </template>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell { height: 100vh; display: flex; flex-direction: column; }
.top { height: 50px; flex: none; background: var(--navy); color: #fff; padding: 0 16px; display: flex; align-items: center; gap: 14px; }
.brand { font-size: 15px; font-weight: 700; white-space: nowrap; }
.tag { font-size: 11px; opacity: .65; margin-left: -2px; white-space: nowrap; }
.spacer { flex: 1; }
.who { display: flex; flex-direction: column; white-space: nowrap; gap: 1px; }
.who small { font-size: 11px; opacity: .85; }
.out { height: 26px; padding: 0 9px; font-size: 12px; border-radius: 5px; background: none; color: #fff; border: 1px solid #3b5a8c; cursor: pointer; white-space: nowrap; }
.body { flex: 1; display: flex; min-height: 0; }
.menu { width: 230px; flex: none; background: #fff; border-right: 1px solid var(--line); overflow-y: auto; }
.menu-label { font-size: 11px; letter-spacing: 1px; color: var(--muted); padding: 14px 14px 6px; }
.item { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 30px; padding: 7px 14px; border: 0; background: none; cursor: pointer; text-align: left; }
.item:hover { background: #eef3fb; }
.item.sub { padding-left: 34px; }
.item.on { background: var(--sel); color: var(--pri-d); font-weight: 700; }
.item i { width: 12px; text-align: center; font-style: normal; flex: none; }
.item i.arrow { font-size: 9px; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.tabs { height: 37px; flex: none; border-bottom: 1px solid var(--line); background: var(--tabs-bg); padding: 6px 8px 0; display: flex; gap: 2px; overflow: hidden; }
.tab { height: 30px; border-radius: 6px 6px 0 0; font-size: 12.5px; background: var(--tab-off); padding: 0 6px 0 12px; display: flex; align-items: center; gap: 8px; cursor: pointer; white-space: nowrap; }
.tab.on { background: #fff; color: var(--navy); font-weight: 700; }
.x { width: 18px; height: 18px; border-radius: 50%; border: 0; background: none; cursor: pointer; line-height: 1; padding: 0; color: var(--muted); }
.x:hover { background: var(--err); color: #fff; }
.others { margin-left: auto; align-self: center; margin-top: -2px; flex: none; }
.work { flex: 1; min-height: 0; overflow: auto; padding: 14px 18px 24px; background: var(--bg); }
@media (max-width: 720px) {
  .menu { width: 160px; }
  .tag, .who small { display: none; }
}
</style>
