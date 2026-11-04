// 화면 토큰 → 화면 컴포넌트
import { defineAsyncComponent } from 'vue'

const lazy = (loader) => defineAsyncComponent(loader)

export const SCREENS = {
  dashboard: lazy(() => import('./dashboard/DashboardScreen.vue')),
  'hull-list': lazy(() => import('./hull/HullListScreen.vue')),
  'plan-gantt': lazy(() => import('./plan/PlanGanttScreen.vue')),
  progress: lazy(() => import('./progress/ProgressScreen.vue')),
  'dwg-list': lazy(() => import('./drawing/DrawingListScreen.vue')),
  'dwg-approval': lazy(() => import('./approval/ApprovalScreen.vue')),
  'user-mgmt': lazy(() => import('./user/UserScreen.vue')),
}
