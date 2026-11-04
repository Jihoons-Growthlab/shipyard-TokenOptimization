import { createRouter, createWebHistory } from 'vue-router'
import { session } from './stores/session'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/', component: () => import('./views/ShellView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  if (!session.token && !to.meta.public) return '/login'
  if (session.token && to.path === '/login') return '/'
  return true
})
