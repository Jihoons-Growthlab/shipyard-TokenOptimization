import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { configureSession } from './stores/session'
import './styles.css'

configureSession(router)
createApp(App).use(router).mount('#app')
