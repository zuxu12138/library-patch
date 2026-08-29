import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  { path: "/", redirect: "/findbook" },
  { path: "/findbook", component: () => import("../views/FindBookView.vue") },
  { path: "/knowledge", component: () => import("../views/KnowledgeMapView.vue") },
  { path: "/seat", component: () => import("../views/SeatPredictView.vue") },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
