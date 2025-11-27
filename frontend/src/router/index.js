import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Ingestion from '../views/Ingestion.vue'
import Query from '../views/Query.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home
    },
    {
      path: '/ingestion',
      name: 'ingestion',
      component: Ingestion
    },
    {
      path: '/query',
      name: 'query',
      component: Query
    }
  ]
})

export default router

