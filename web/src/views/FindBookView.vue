<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { searchBooks, sendFeedback, type Book, type FindBookResult, type Holding } from "../api/findbook";
import ErrorState from "../components/ErrorState.vue";
import FeedbackFab from "../components/FeedbackFab.vue";
import LoadingState from "../components/LoadingState.vue";

const query = ref("");
const result = ref<FindBookResult | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const lastQuery = ref("");
const feedbackOpen = ref(false);
const page = ref(1);
const pageSize = 10;
const searchInput = ref<HTMLInputElement | null>(null);

// 最近检索(localStorage, 最多 8 条)
const RECENT_KEY = "library-patch-recent-searches";
const recent = ref<string[]>([]);
const HOT_CLASSES = ["深度学习", "机器学习", "鲁迅", "数据结构", "建筑史"];
const showSuggest = ref(false);
const activeSuggest = ref(-1);

const suggests = computed(() => {
  const list = query.value.trim()
    ? recent.value.filter((r) => r !== query.value.trim() && r.includes(query.value.trim()))
    : recent.value;
  return [...list, ...HOT_CLASSES.filter((h) => !list.includes(h))].slice(0, 8);
});

function loadRecent() {
  try {
    recent.value = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
  } catch {
    recent.value = [];
  }
}

function pushRecent(q: string) {
  recent.value = [q, ...recent.value.filter((r) => r !== q)].slice(0, 8);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.value));
}

// ⌘K 或 / 聚焦, Esc 清空失焦
function onGlobalKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName;
  const typing = tag === "INPUT" || tag === "TEXTAREA";
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    searchInput.value?.focus();
  } else if (e.key === "/" && !typing) {
    e.preventDefault();
    searchInput.value?.focus();
  } else if (e.key === "Escape" && typing) {
    query.value = "";
    (e.target as HTMLElement).blur();
  }
}

function onInputBlur() {
  // 延迟收起联想, 让 mousedown 先命中选项
  window.setTimeout(() => (showSuggest.value = false), 150);
}

function onInputKeydown(e: KeyboardEvent) {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const delta = e.key === "ArrowDown" ? 1 : -1;
    const len = suggests.value.length;
    if (len) activeSuggest.value = (activeSuggest.value + delta + len) % len;
  } else if (e.key === "Enter" && activeSuggest.value >= 0 && suggests.value[activeSuggest.value]) {
    e.preventDefault();
    query.value = suggests.value[activeSuggest.value];
    activeSuggest.value = -1;
    search();
  }
}

onMounted(() => {
  loadRecent();
  window.addEventListener("keydown", onGlobalKeydown);
});
onBeforeUnmount(() => window.removeEventListener("keydown", onGlobalKeydown));

function holdingStatus(h: Holding): "in" | "out" | "unknown" {
  const s = h.status?.trim() ?? "";
  if (s.includes("可借") && !s.includes("不可借")) return "in";
  if (s.includes("借出") || s.includes("不可借")) return "out";
  if (s.includes("在馆") || h.available) return "in";
  return "unknown";
}

function availableCount(book: Book): number {
  return (book.holdings ?? []).filter((h) => holdingStatus(h) === "in").length;
}

const expanded = ref<Set<string>>(new Set());
function toggleHoldings(bibId: string) {
  const next = new Set(expanded.value);
  if (next.has(bibId)) next.delete(bibId);
  else next.add(bibId);
  expanded.value = next;
}

async function search(toPage = 1) {
  if (!query.value.trim()) return;
  loading.value = true;
  errorMessage.value = "";
  result.value = null;
  lastQuery.value = query.value.trim();
  page.value = toPage;
  showSuggest.value = false;
  activeSuggest.value = -1;
  try {
    result.value = await searchBooks(lastQuery.value, toPage, pageSize);
    pushRecent(lastQuery.value);
    expanded.value = new Set();
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : "出了点问题，请稍后再试";
  } finally {
    loading.value = false;
  }
}

function pickSuggest(s: string) {
  query.value = s;
  showSuggest.value = false;
  search();
}

const totalPages = computed(() => (result.value ? Math.max(1, Math.ceil(result.value.total / pageSize)) : 1));

async function submitFeedback(text: string) {
  return await sendFeedback(text);
}
</script>

<template>
  <section class="findbook">
    <header class="page-head">
      <h1 class="page-title">找书</h1>
      <p class="page-sub">说出你想读什么，剩下的交给书架</p>
    </header>

    <!-- 命令式搜索框: Raycast 风格 -->
    <form class="command" role="search" @submit.prevent="search()">
      <div class="command-box" :class="{ focused: showSuggest }">
        <input
          ref="searchInput"
          v-model="query"
          type="text"
          placeholder="输入书名、作者或关键词…"
          aria-label="检索馆藏"
          autocomplete="off"
          @focus="showSuggest = true"
          @blur="onInputBlur"
          @keydown="onInputKeydown"
        />
        <kbd class="hint-key" aria-hidden="true">⌘K</kbd>
      </div>
      <div v-if="showSuggest && suggests.length" class="suggest" role="listbox">
        <button
          v-for="(s, i) in suggests"
          :key="s"
          type="button"
          role="option"
          class="suggest-item"
          :class="{ active: i === activeSuggest }"
          @mousedown.prevent="pickSuggest(s)"
        >
          {{ s }}
        </button>
      </div>
    </form>

    <LoadingState v-if="loading" :rows="4" />
    <ErrorState v-else-if="errorMessage" :message="errorMessage" />

    <div v-else-if="result" class="results">
      <p class="result-meta">
        「{{ lastQuery }}」共 <strong>{{ result.total }}</strong> 条 · 第 {{ page }} / {{ totalPages }} 页
      </p>

      <ul v-if="result.books.length" class="book-grid">
        <li
          v-for="(book, i) in result.books"
          :key="book.bibId"
          class="book-card rise-in"
          :style="{ animationDelay: `${i * 50}ms` }"
        >
          <div class="book-head">
            <span class="class-no">{{ book.classNo || "—" }}</span>
            <h2 class="book-title">{{ book.title }}</h2>
            <p class="book-meta">{{ book.author || "佚名" }}</p>
            <p class="book-meta dim">{{ book.publisher }} · {{ book.pubYear || "—" }}</p>
          </div>

          <div class="book-callno" v-if="book.callNos?.length">
            <span class="mono-label">索书号</span>
            <span class="mono">{{ book.callNos.join(" / ") }}</span>
          </div>

          <!-- holdings 翻牌展开 -->
          <button
            v-if="book.holdings?.length"
            type="button"
            class="holdings-toggle"
            :aria-expanded="expanded.has(book.bibId)"
            @click="toggleHoldings(book.bibId)"
          >
            <span class="dot" :class="availableCount(book) > 0 ? 'in' : 'out'"></span>
            {{ availableCount(book) }} 册可借 · 共 {{ book.holdings.length }} 册
            <span class="chevron" aria-hidden="true">{{ expanded.has(book.bibId) ? "▴" : "▾" }}</span>
          </button>

          <div v-if="expanded.has(book.bibId)" class="holdings-table-wrap">
            <table class="holdings-table">
              <thead>
                <tr><th>索书号</th><th>架位</th><th>状态</th></tr>
              </thead>
              <tbody>
                <tr v-for="h in book.holdings" :key="h.barCode">
                  <td class="mono">{{ h.callNo }}</td>
                  <td>{{ h.location }}</td>
                  <td>
                    <span class="badge" :class="holdingStatus(h)">
                      {{ holdingStatus(h) === "in" ? "可借" : holdingStatus(h) === "out" ? "已借出" : h.status || "未知" }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </li>
      </ul>

      <div v-else class="empty-state">
        <p class="empty-title">书架的这一层是空的</p>
        <p class="empty-sub">没有找到「{{ lastQuery }}」，换个关键词，或用作者名、ISBN 试试</p>
      </div>

      <!-- 分页: 基于真实 total -->
      <nav v-if="totalPages > 1" class="pager" aria-label="分页">
        <button type="button" :disabled="page <= 1" @click="search(page - 1)">上一页</button>
        <span class="pager-info">{{ page }} / {{ totalPages }}</span>
        <button type="button" :disabled="page >= totalPages" @click="search(page + 1)">下一页</button>
      </nav>
    </div>

    <p v-else class="empty-invite">
      按 <kbd>/</kbd> 或 <kbd>⌘K</kbd> 开始检索 —— 结果会像抽书一样逐本浮现
    </p>

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
  margin-bottom: 2rem;
}

.page-title {
  font-family: var(--font-serif);
  font-size: 2.25rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 0;
}

.page-sub {
  margin: 0.5rem 0 0;
  color: var(--color-ink-soft);
  font-size: 15px;
}

/* 命令式搜索 */
.command {
  position: relative;
  max-width: 640px;
  margin: 0 auto 2.5rem;
}

.command-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 60px;
  padding: 0 1.25rem;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  transition: border-color 0.2s ease;
}

.command-box.focused,
.command-box:focus-within {
  border-color: var(--color-teal);
}

.command-box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 18px;
  font-family: var(--font-sans);
  color: var(--color-ink);
}

.command-box input::placeholder {
  color: var(--color-ink-muted);
}

.hint-key {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-muted);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 0.15rem 0.45rem;
}

.suggest {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 10;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 0.35rem;
  display: flex;
  flex-direction: column;
}

.suggest-item {
  text-align: left;
  border: none;
  background: transparent;
  padding: 0.55rem 0.75rem;
  font-size: 14px;
  color: var(--color-ink-soft);
  cursor: pointer;
  border-radius: 2px;
  min-height: 44px;
}

.suggest-item:hover,
.suggest-item.active {
  background: var(--color-paper);
  color: var(--color-teal);
}

/* 结果 */
.result-meta {
  margin: 0 0 1.25rem;
  color: var(--color-ink-soft);
  font-size: 14px;
  border-bottom: 1px solid var(--color-line);
  padding-bottom: 0.75rem;
}

.result-meta strong {
  color: var(--color-teal);
  font-family: var(--font-mono);
}

.book-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}

/* 书架隐喻: hover 如抽出一本书 */
.book-card {
  display: flex;
  flex-direction: column;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 1.1rem 1.15rem;
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.2s ease;
}

.book-card:hover {
  transform: perspective(800px) rotateX(2deg) translateY(-4px);
  border-color: var(--color-teal);
}

.class-no {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--color-teal);
}

.book-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0.4rem 0 0.3rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.book-meta {
  margin: 0;
  font-size: 13px;
  color: var(--color-ink-soft);
  line-height: 1.5;
}

.book-meta.dim {
  color: var(--color-ink-muted);
  font-size: 12px;
}

.book-callno {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-top: 0.75rem;
  padding-top: 0.6rem;
  border-top: 1px dashed var(--color-line);
}

.mono-label {
  font-size: 11px;
  color: var(--color-ink-muted);
  letter-spacing: 0.1em;
}

.mono {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--color-ink);
}

/* holdings 翻牌 */
.holdings-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
  padding: 0.45rem 0;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--color-ink-soft);
  cursor: pointer;
  text-align: left;
  min-height: 44px;
}

.holdings-toggle:hover {
  color: var(--color-teal);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot.in { background: var(--color-available); }
.dot.out { background: var(--color-ink-muted); }

.chevron {
  margin-left: auto;
  font-size: 11px;
  color: var(--color-ink-muted);
}

.holdings-table-wrap {
  overflow: hidden;
  animation: flip-open 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes flip-open {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.holdings-table th {
  text-align: left;
  font-weight: 500;
  color: var(--color-ink-muted);
  padding: 0.35rem 0.4rem;
  border-bottom: 1px solid var(--color-line);
  font-size: 11px;
  letter-spacing: 0.08em;
}

.holdings-table td {
  padding: 0.4rem;
  border-bottom: 1px solid var(--color-line);
  color: var(--color-ink-soft);
  vertical-align: top;
}

.badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  font-size: 11.5px;
  border-radius: 2px;
}

.badge.in {
  color: var(--color-available);
  background: var(--color-available-bg);
}

.badge.out,
.badge.unknown {
  color: var(--color-ink-muted);
  background: var(--color-paper);
  border: 1px solid var(--color-line);
}

/* 空态 */
.empty-state {
  text-align: center;
  padding: 3.5rem 1rem;
}

.empty-title {
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 600;
  margin: 0;
}

.empty-sub {
  margin: 0.5rem 0 0;
  color: var(--color-ink-soft);
  font-size: 14px;
}

.empty-invite {
  text-align: center;
  color: var(--color-ink-muted);
  margin: 3rem 0 0;
  font-size: 14px;
}

.empty-invite kbd {
  font-family: var(--font-mono);
  font-size: 11px;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  padding: 0.1rem 0.4rem;
  background: var(--color-card);
}

/* 分页 */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.25rem;
  margin-top: 2.25rem;
}

.pager button {
  min-height: 44px;
  padding: 0.4rem 1.1rem;
  border: 1px solid var(--color-line);
  border-radius: 2px;
  background: var(--color-card);
  color: var(--color-ink);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.pager button:hover:not(:disabled) {
  border-color: var(--color-teal);
  color: var(--color-teal);
}

.pager button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pager-info {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--color-ink-muted);
}

@media (max-width: 640px) {
  .page-title {
    font-size: 1.7rem;
  }
  .command-box {
    height: 52px;
  }
  .command-box input {
    font-size: 16px;
  }
  .book-grid {
    grid-template-columns: 1fr;
  }
}
</style>
