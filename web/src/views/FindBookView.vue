<script setup lang="ts">
import { ref } from "vue";
import { searchBooks, sendFeedback, type FindBookResult, type Holding } from "../api/findbook";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const query = ref("");
const result = ref<FindBookResult | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const lastQuery = ref("");
const feedbackOpen = ref(false);

function holdingStatus(h: Holding): "in" | "out" | "unknown" {
  const s = h.status?.trim() ?? "";
  if (s.includes("借出") || s.includes("不可借") || s.includes("可借")) return s.includes("可借") && !s.includes("不可借") ? "in" : "out";
  if (s.includes("在馆") || h.available) return "in";
  return "unknown";
}

async function search() {
  if (!query.value.trim()) return;
  loading.value = true;
  errorMessage.value = "";
  result.value = null;
  lastQuery.value = query.value.trim();
  try {
    result.value = await searchBooks(lastQuery.value);
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

async function submitFeedback(text: string) {
  return await sendFeedback(text);
}
</script>

<template>
  <section class="findbook">
    <header class="page-head">
      <h1 class="page-title">找书</h1>
      <p class="page-sub">检索馆藏图书，查看索书号与借阅状态</p>
    </header>

    <form @submit.prevent="search" class="searchbar" role="search">
      <span class="search-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" width="20" height="20">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" />
          <line x1="20" y1="20" x2="16.5" y2="16.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </span>
      <input
        v-model="query"
        type="search"
        placeholder="输入书名、作者或关键词..."
        aria-label="检索馆藏"
      />
      <button type="submit">搜索</button>
    </form>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <div v-else-if="result" class="results">
      <p class="result-meta">
        共 <strong>{{ result.total }}</strong> 条结果
      </p>

      <ul v-if="result.books.length" class="book-grid">
        <li v-for="book in result.books" :key="book.bibId" class="book-card">
          <div class="cover" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" width="34" height="34">
              <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
            </svg>
            <span class="cover-label">DUT 图书馆</span>
          </div>
          <div class="book-body">
            <h2 class="book-title">{{ book.title }}</h2>
            <p class="book-author">{{ book.author || "佚名" }}</p>
            <div class="book-foot">
              <span
                class="status-tag"
                :class="holdingStatus(book.holdings?.[0] ?? ({} as Holding))"
              >
                {{ (book.holdings?.[0]?.status ?? "未知") }}
              </span>
              <span class="book-year">{{ book.pubYear || "—" }}</span>
            </div>
          </div>
        </li>
      </ul>

      <div v-else class="empty-state">
        <div class="empty-illustration" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" width="56" height="56">
            <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
            <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
            <path d="M9 8h6M9 11h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
          </svg>
        </div>
        <p class="empty-title">没有找到「{{ lastQuery }}」</p>
        <p class="empty-sub">换个关键词，或用作者名、ISBN 试试</p>
      </div>
    </div>

    <p v-else class="empty-invite">输入关键词开始检索，结果会以卡片展示</p>

    <FeedbackFab
      :open="feedbackOpen"
      :on-submit="submitFeedback"
      @toggle="feedbackOpen = !feedbackOpen"
    />
  </section>
</template>

<style scoped>
.page-head {
  text-align: center;
  margin-bottom: 1.75rem;
}

.page-title {
  font-size: var(--fs-page);
  color: var(--ink);
}

.page-sub {
  margin: 0.4rem 0 0;
  color: var(--ink-soft);
  font-size: var(--fs-body);
}

.searchbar {
  position: relative;
  display: flex;
  align-items: center;
  width: 600px;
  max-width: 100%;
  height: 52px;
  margin: 0 auto 2rem;
  background: var(--card);
  border: 1.5px solid var(--line);
  border-radius: 26px;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.searchbar:focus-within {
  border-color: var(--dut-blue);
  box-shadow: 0 0 0 4px rgba(0, 61, 165, 0.12);
}

.search-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 46px;
  color: var(--ink-muted);
}

.searchbar input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--fs-body);
  padding: 0 0.25rem;
}

.searchbar input::placeholder {
  color: var(--ink-muted);
}

.searchbar button {
  flex-shrink: 0;
  align-self: stretch;
  padding: 0 1.5rem;
  border: none;
  background: var(--dut-blue);
  color: #fff;
  font-size: var(--fs-body);
  font-weight: 600;
  transition: background 0.2s ease;
}

.searchbar button:hover {
  background: var(--dut-blue-bright);
}

.result-meta {
  margin: 0 0 1rem;
  color: var(--ink-soft);
  font-size: 14px;
}

.result-meta strong {
  color: var(--dut-blue);
}

.book-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1.25rem;
}

.book-card {
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.book-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-hover);
  border-color: var(--dut-blue-light);
}

.cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  height: 132px;
  color: var(--dut-blue);
  background: linear-gradient(160deg, var(--dut-blue-light), #f5f8ff);
}

.cover-label {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--ink-muted);
}

.book-body {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.9rem 1rem 1rem;
}

.book-title {
  font-size: var(--fs-body);
  font-weight: 700;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.book-author {
  margin: 0;
  color: var(--ink-soft);
  font-size: 13px;
}

.book-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.2rem;
}

.status-tag {
  font-size: 12px;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  font-weight: 500;
}

.status-tag.in {
  color: var(--available);
  background: var(--available-bg);
}

.status-tag.out,
.status-tag.unknown {
  color: var(--unavailable);
  background: var(--unavailable-bg);
}

.book-year {
  font-size: 12px;
  color: var(--ink-muted);
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
}

.empty-illustration {
  color: var(--ink-muted);
  margin-bottom: 0.75rem;
}

.empty-title {
  margin: 0;
  font-size: var(--fs-module);
  font-weight: 600;
}

.empty-sub {
  margin: 0.3rem 0 0;
  color: var(--ink-soft);
  font-size: 14px;
}

.empty-invite {
  text-align: center;
  color: var(--ink-muted);
  margin: 2rem 0 0;
}

@media (max-width: 640px) {
  .searchbar button {
    padding: 0 1rem;
  }
}
</style>
