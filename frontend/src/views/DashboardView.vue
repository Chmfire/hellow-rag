<template>
  <div class="dashboard">

    <!-- Hero search -->
    <div class="hero">
      <div class="hero-eyebrow">Enterprise Knowledge Base</div>
      <h1 class="hero-title">
        Ask anything about your
        <span class="gradient-text">knowledge base</span>
      </h1>
      <p class="hero-subtitle">
        Leverage AI to extract insights from your documents instantly
      </p>
      <div class="search-bar" :class="{ focused: searchFocused }">
        <el-icon class="search-icon"><search /></el-icon>
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="Ask a question or search documents..."
          @focus="searchFocused = true"
          @blur="searchFocused = false"
          @keydown.enter="handleSearch"
        />
        <button class="search-submit" @click="handleSearch" :disabled="searching">
          <span v-if="!searching">Ask AI</span>
          <span v-else class="searching-dots"><span/><span/><span/></span>
        </button>
      </div>
      <transition name="slide-up">
        <div v-if="aiAnswer" class="ai-result">
          <div class="ai-result-header">
            <div class="ai-badge"><el-icon><cpu /></el-icon> AI Answer</div>
            <button class="close-btn" @click="aiAnswer = ''">×</button>
          </div>
          <div class="ai-result-body" v-html="aiAnswer" />
        </div>
      </transition>
    </div>

    <!-- Bento Grid -->
    <div class="bento">

      <!-- Stats row -->
      <div class="bento-stats">
        <div class="stat-card" v-for="s in stats" :key="s.label" @mouseenter="handleStatHover(s.label)" @mouseleave="handleStatLeave">
          <div class="stat-icon-wrap" :style="{ '--c': s.color }">
            <el-icon class="stat-icon"><component :is="s.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
          <div class="stat-glow" :style="{ background: s.color }" />
          <div class="stat-ripple" v-if="hoveredStat === s.label" />
        </div>
      </div>

      <!-- Main row -->
      <div class="bento-main">

        <!-- Collections card (wide) -->
        <div class="bento-card collections-card">
          <div class="bento-card-header">
            <span class="bento-card-title">Knowledge Bases</span>
            <button class="link-btn" @click="$emit('navigate', 'admin-collections')">
              View all <el-icon><arrow-right /></el-icon>
            </button>
          </div>
          <div class="collections-list">
            <div v-for="col in collections.slice(0, 5)" :key="col.collection_name"
              class="col-row" @click="$emit('navigate', 'admin-collections')">
              <div class="col-icon">
                <el-icon><data-analysis /></el-icon>
              </div>
              <div class="col-info">
                <div class="col-name">{{ col.collection_name }}</div>
                <div class="col-meta">{{ col.embedding_model || 'text-embedding-v3' }}</div>
              </div>
              <div class="col-tags">
                <span v-if="col.image_mode" class="mini-tag purple">图文</span>
                <span class="mini-tag blue">{{ col.metrics || 'cosine' }}</span>
              </div>
              <div class="col-arrow"><el-icon><arrow-right /></el-icon></div>
            </div>
            <div v-if="collections.length === 0" class="empty-state">
              <el-icon style="font-size:28px;opacity:0.2"><data-analysis /></el-icon>
              <span>No knowledge bases yet</span>
              <button class="empty-action" @click="$emit('navigate', 'admin-create')">
                Create Knowledge Base
              </button>
            </div>
          </div>
        </div>

        <!-- Right column -->
        <div class="bento-right">

          <!-- Quick actions -->
          <div class="bento-card actions-card">
            <div class="bento-card-header">
              <span class="bento-card-title">Quick Actions</span>
            </div>
            <div class="actions-grid">
              <button v-for="a in actions" :key="a.label"
                class="action-btn" :style="{ '--ac': a.color }"
                @click="$emit('navigate', a.route)"
                @mouseenter="handleActionHover(a.label)"
                @mouseleave="handleActionLeave">
                <div class="action-icon"><el-icon><component :is="a.icon" /></el-icon></div>
                <span>{{ a.label }}</span>
                <div class="action-ripple" v-if="hoveredAction === a.label" />
              </button>
            </div>
          </div>

          <!-- System status -->
          <div class="bento-card status-card">
            <div class="bento-card-header">
              <span class="bento-card-title">System</span>
              <div class="live-badge">
                <span class="live-dot" />LIVE
              </div>
            </div>
            <div class="status-rows">
              <div class="status-row" v-for="s in statusItems" :key="s.label">
                <span class="status-name">{{ s.label }}</span>
                <div class="status-indicator" :class="s.ok ? 'ok' : 'err'">
                  <span class="status-dot-sm" />
                  {{ s.ok ? 'Operational' : 'Degraded' }}
                </div>
              </div>
              <div class="status-footer">
                <span class="status-last-updated">Last updated: {{ lastUpdated }}</span>
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Search, Cpu, DataAnalysis, FolderOpened, ChatDotRound, Setting, ArrowRight, Connection } from '@element-plus/icons-vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const emit = defineEmits(['navigate'])
const md = new MarkdownIt({ breaks: true, linkify: true })
const API = 'http://localhost:8001/api/v1'

const searchQuery = ref('')
const searchFocused = ref(false)
const searching = ref(false)
const aiAnswer = ref('')
const collections = ref([])
const hoveredStat = ref(null)
const hoveredAction = ref(null)
const lastUpdated = ref('')

const stats = ref([
  { label: 'Knowledge Bases', value: '—', icon: 'DataAnalysis', color: 'rgba(79,142,247,0.6)' },
  { label: 'Categories',      value: '—', icon: 'FolderOpened',  color: 'rgba(45,212,160,0.6)' },
  { label: 'API Status',      value: '—', icon: 'Connection',    color: 'rgba(167,139,250,0.6)' },
  { label: 'Model',           value: '—', icon: 'Cpu',           color: 'rgba(245,200,66,0.6)' },
])

const actions = [
  { label: '智能对话',   route: 'chat',               icon: 'ChatDotRound', color: '#4f8ef7' },
  { label: '类目管理',   route: 'kb-categories',      icon: 'FolderOpened', color: '#2dd4a0' },
  { label: '知识库列表', route: 'admin-collections',  icon: 'DataAnalysis', color: '#a78bfa' },
  { label: '创建知识库', route: 'admin-create',        icon: 'Setting',      color: '#f5c842' },
]

const statusItems = ref([
  { label: 'API Service',  ok: false },
  { label: 'Backend',      ok: false },
  { label: 'API Key',      ok: false },
])

const handleSearch = async () => {
  if (!searchQuery.value.trim() || searching.value) return
  searching.value = true
  aiAnswer.value = ''
  try {
    const res = await axios.post(`${API}/knowledge/`, { query: searchQuery.value, session_id: 'dashboard' })
    aiAnswer.value = md.render(res.data?.answer || '未找到相关内容')
  } catch {
    aiAnswer.value = md.render('暂时无法连接知识库，请稍后重试。')
  } finally {
    searching.value = false
  }
}

const handleStatHover = (label) => {
  hoveredStat.value = label
}

const handleStatLeave = () => {
  hoveredStat.value = null
}

const handleActionHover = (label) => {
  hoveredAction.value = label
}

const handleActionLeave = () => {
  hoveredAction.value = null
}

const formatLastUpdated = () => {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

onMounted(async () => {
  lastUpdated.value = formatLastUpdated()
  try {
    const [colRes, healthRes] = await Promise.allSettled([
      axios.get(`${API}/admin/collections`),
      axios.get(`${API}/health`),
    ])
    if (colRes.status === 'fulfilled') {
      collections.value = colRes.value.data?.data?.collections || []
      stats.value[0].value = collections.value.length
      statusItems.value[0].ok = true
    }
    if (healthRes.status === 'fulfilled') {
      const h = healthRes.value.data
      statusItems.value[1].ok = h?.status === 'healthy'
      statusItems.value[2].ok = h?.api_key_configured ?? false
      stats.value[2].value = h?.status === 'healthy' ? 'Online' : 'Offline'
      stats.value[3].value = h?.default_model || '—'
    }
    try {
      const catRes = await axios.get(`${API}/categories`)
      stats.value[1].value = catRes.data?.data?.total ?? '—'
    } catch {}
  } catch {}
  
  // 更新时间
  setInterval(() => {
    lastUpdated.value = formatLastUpdated()
  }, 60000)
})
</script>

<style scoped>
.dashboard { max-width: 1400px; margin: 0 auto; }

/* ── Hero ── */
.hero { margin-bottom: 48px; text-align: center; }
.hero-eyebrow {
  font-size: 12px; font-weight: 600; letter-spacing: 2px;
  text-transform: uppercase; color: rgba(79,142,247,0.8);
  margin-bottom: 16px;
  animation: fadeInUp 0.6s ease-out;
}
.hero-title {
  font-size: 42px; font-weight: 800; line-height: 1.1;
  color: #f0f4ff; margin-bottom: 16px;
  letter-spacing: -1px;
  animation: fadeInUp 0.8s ease-out 0.2s both;
}
.hero-subtitle {
  font-size: 16px; color: rgba(255,255,255,0.4);
  margin-bottom: 32px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
  animation: fadeInUp 0.8s ease-out 0.4s both;
}
.gradient-text {
  background: linear-gradient(135deg, #7eb3ff 0%, #a78bfa 50%, #34d399 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  position: relative;
}
.gradient-text::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(135deg, #7eb3ff, #a78bfa, #34d399);
  border-radius: 2px;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s ease;
}
.hero-title:hover .gradient-text::after {
  transform: scaleX(1);
}

/* ── Search bar ── */
.search-bar {
  display: flex; align-items: center; gap: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px; padding: 14px 20px;
  backdrop-filter: blur(20px);
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  max-width: 720px;
  margin: 0 auto;
  animation: fadeInUp 0.8s ease-out 0.6s both;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.search-bar.focused {
  border-color: rgba(79,142,247,0.5);
  box-shadow: 0 0 0 4px rgba(79,142,247,0.12), 0 12px 40px rgba(0,0,0,0.3);
  background: rgba(255,255,255,0.06);
  transform: translateY(-2px);
}
.search-icon { font-size: 20px; color: rgba(255,255,255,0.4); flex-shrink: 0; transition: color 0.3s ease; }
.search-bar.focused .search-icon { color: rgba(255,255,255,0.7); }
.search-input {
  flex: 1; background: transparent; border: none; outline: none;
  color: #f0f4ff; font-size: 16px; caret-color: #7eb3ff;
  font-weight: 400;
}
.search-input::placeholder { color: rgba(255,255,255,0.25); }
.search-submit {
  background: linear-gradient(135deg, #3b6fd4, #5b4fcf);
  border: none; border-radius: 12px; padding: 10px 20px;
  color: #fff; font-size: 14px; font-weight: 600; cursor: pointer;
  flex-shrink: 0; transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  box-shadow: 0 4px 16px rgba(59,111,212,0.5);
  position: relative;
  overflow: hidden;
}
.search-submit::before {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
  transition: left 0.6s ease;
}
.search-submit:hover::before {
  left: 100%;
}
.search-submit:hover { 
  box-shadow: 0 6px 24px rgba(59,111,212,0.7); 
  transform: translateY(-2px); 
}
.search-submit:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
.searching-dots { display: flex; gap: 4px; align-items: center; }
.searching-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: #fff;
  animation: dot-bounce 1.2s infinite;
}
.searching-dots span:nth-child(2) { animation-delay: 0.2s; }
.searching-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }

/* ── AI Result ── */
.ai-result {
  margin-top: 20px; max-width: 720px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(79,142,247,0.2);
  border-radius: 16px; padding: 20px 24px;
  backdrop-filter: blur(20px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.25);
  margin-left: auto;
  margin-right: auto;
}
.ai-result-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.ai-badge {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; font-weight: 600; color: #7eb3ff;
  text-transform: uppercase; letter-spacing: 0.8px;
  background: rgba(79,142,247,0.1);
  padding: 4px 12px;
  border-radius: 99px;
  border: 1px solid rgba(79,142,247,0.2);
}
.close-btn {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.4);
  font-size: 18px; cursor: pointer; line-height: 1; padding: 4px 8px;
  border-radius: 8px;
  transition: all 0.3s ease;
}
.close-btn:hover {
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.8);
  transform: scale(1.1);
}
.ai-result-body { font-size: 14px; line-height: 1.7; color: #94a3b8; }
.ai-result-body :deep(p) { margin: 6px 0; }
.ai-result-body :deep(code) { background: rgba(255,255,255,0.08); border-radius: 4px; padding: 2px 6px; font-size: 13px; color: #7eb3ff; }
.ai-result-body :deep(ul),
.ai-result-body :deep(ol) { margin: 8px 0; padding-left: 20px; }
.ai-result-body :deep(li) { margin: 4px 0; }

/* ── Bento ── */
.bento { display: flex; flex-direction: column; gap: 20px; }

/* Stats row */
.bento-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  position: relative; overflow: hidden;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 20px; padding: 20px 24px;
  display: flex; align-items: center; gap: 16px;
  backdrop-filter: blur(20px);
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.stat-card:hover {
  border-color: rgba(255,255,255,0.12);
  transform: translateY(-4px);
  box-shadow: 0 16px 48px rgba(0,0,0,0.4);
}
.stat-icon-wrap {
  width: 48px; height: 48px; border-radius: 14px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; color: #fff;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  transition: all 0.3s ease;
}
.stat-card:hover .stat-icon-wrap {
  transform: scale(1.1);
  box-shadow: 0 0 24px var(--c);
}
.stat-icon {
  transition: all 0.3s ease;
}
.stat-card:hover .stat-icon {
  transform: rotate(5deg);
}
.stat-value { font-size: 28px; font-weight: 800; color: #f0f4ff; line-height: 1; letter-spacing: -0.5px; }
.stat-label { font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat-glow {
  position: absolute; bottom: -20px; right: -20px;
  width: 100px; height: 100px; border-radius: 50%;
  filter: blur(40px); opacity: 0.15; pointer-events: none;
  transition: all 0.3s ease;
}
.stat-card:hover .stat-glow {
  opacity: 0.25;
  transform: scale(1.2);
}
.stat-ripple {
  position: absolute;
  top: 50%; left: 50%;
  width: 0; height: 0;
  border-radius: 50%;
  background: rgba(255,255,255,0.1);
  transform: translate(-50%, -50%);
  animation: ripple 1.5s ease-out infinite;
}
@keyframes ripple {
  0% {
    width: 0;
    height: 0;
    opacity: 0.5;
  }
  100% {
    width: 200px;
    height: 200px;
    opacity: 0;
  }
}

/* Main row */
.bento-main { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
.bento-right { display: flex; flex-direction: column; gap: 20px; }

/* Generic bento card */
.bento-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 20px; padding: 24px;
  backdrop-filter: blur(20px);
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
}
.bento-card:hover {
  border-color: rgba(255,255,255,0.11);
  box-shadow: 0 12px 40px rgba(0,0,0,0.35);
  transform: translateY(-2px);
}
.bento-card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px;
}
.bento-card-title {
  font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.4);
  text-transform: uppercase; letter-spacing: 1px;
  background: rgba(255,255,255,0.05);
  padding: 4px 12px;
  border-radius: 99px;
  border: 1px solid rgba(255,255,255,0.08);
}
.link-btn {
  display: flex; align-items: center; gap: 4px;
  background: rgba(79,142,247,0.1);
  border: 1px solid rgba(79,142,247,0.2);
  color: #7eb3ff;
  font-size: 12px; cursor: pointer; padding: 6px 12px;
  border-radius: 99px;
  transition: all 0.3s ease;
}
.link-btn:hover {
  gap: 8px;
  background: rgba(79,142,247,0.2);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(79,142,247,0.3);
}

/* Collections */
.collections-list { display: flex; flex-direction: column; gap: 8px; }
.col-row {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 16px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  border: 1px solid transparent;
  position: relative;
  overflow: hidden;
}
.col-row::before {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(79,142,247,0.1), transparent);
  transition: left 0.6s ease;
}
.col-row:hover::before {
  left: 100%;
}
.col-row:hover {
  background: rgba(255,255,255,0.04);
  border-color: rgba(79,142,247,0.2);
  transform: translateX(4px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}
.col-icon {
  width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0;
  background: rgba(79,142,247,0.1); border: 1px solid rgba(79,142,247,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; color: #7eb3ff;
  transition: all 0.3s ease;
}
.col-row:hover .col-icon {
  transform: scale(1.1);
  box-shadow: 0 0 16px rgba(79,142,247,0.4);
}
.col-info {
  flex: 1;
  min-width: 0;
}
.col-name { font-size: 14px; color: #e2e8f0; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-meta { font-size: 12px; color: rgba(255,255,255,0.3); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.col-tags { display: flex; gap: 6px; margin-left: 8px; flex-shrink: 0; }
.mini-tag {
  font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 6px;
  text-transform: uppercase; letter-spacing: 0.3px;
  transition: all 0.3s ease;
}
.mini-tag.blue { background: rgba(79,142,247,0.12); color: #7eb3ff; border: 1px solid rgba(79,142,247,0.2); }
.mini-tag.purple { background: rgba(167,139,250,0.12); color: #a78bfa; border: 1px solid rgba(167,139,250,0.2); }
.col-row:hover .mini-tag {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(79,142,247,0.3);
}
.col-arrow {
  color: rgba(255,255,255,0.3);
  font-size: 14px;
  transition: all 0.3s ease;
  flex-shrink: 0;
}
.col-row:hover .col-arrow {
  color: #7eb3ff;
  transform: translateX(4px);
}
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 40px 0;
  color: rgba(255,255,255,0.2);
  font-size: 14px;
  text-align: center;
}
.empty-action {
  margin-top: 8px;
  background: linear-gradient(135deg, #4f8ef7, #7c3aed);
  border: none;
  border-radius: 10px;
  padding: 8px 16px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 16px rgba(79,142,247,0.4);
}
.empty-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(79,142,247,0.6);
}

/* Actions */
.actions-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.action-btn {
  position: relative;
  overflow: hidden;
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 16px 12px;
  border-radius: 16px;
  cursor: pointer;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.5);
  font-size: 13px;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
}
.action-btn:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.9);
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.3);
}
.action-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; color: var(--ac);
  background: color-mix(in srgb, var(--ac) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--ac) 25%, transparent);
  transition: all 0.3s ease;
  position: relative;
  z-index: 1;
}
.action-btn:hover .action-icon {
  transform: scale(1.1);
  box-shadow: 0 0 24px color-mix(in srgb, var(--ac) 40%, transparent);
}
.action-ripple {
  position: absolute;
  top: 50%; left: 50%;
  width: 0; height: 0;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ac) 10%, transparent);
  transform: translate(-50%, -50%);
  animation: ripple 2s ease-out infinite;
}

/* Status */
.live-badge {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; font-weight: 700; color: #2dd4a0;
  text-transform: uppercase; letter-spacing: 1px;
  background: rgba(45,212,160,0.1);
  padding: 4px 12px;
  border-radius: 99px;
  border: 1px solid rgba(45,212,160,0.2);
  transition: all 0.3s ease;
}
.live-badge:hover {
  background: rgba(45,212,160,0.2);
  box-shadow: 0 4px 16px rgba(45,212,160,0.3);
}
.live-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #2dd4a0;
  animation: pulse-green 2s infinite;
  box-shadow: 0 0 0 0 rgba(45,212,160,0.4);
}
@keyframes pulse-green {
  0%   { box-shadow: 0 0 0 0 rgba(45,212,160,0.4); }
  70%  { box-shadow: 0 0 0 8px rgba(45,212,160,0); }
  100% { box-shadow: 0 0 0 0 rgba(45,212,160,0); }
}
.status-rows { display: flex; flex-direction: column; gap: 12px; }
.status-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  transition: all 0.3s ease;
}
.status-row:last-child {
  border-bottom: none;
}
.status-row:hover {
  background: rgba(255,255,255,0.02);
  padding-left: 8px;
  border-radius: 8px;
}
.status-name { font-size: 14px; color: rgba(255,255,255,0.4); font-weight: 500; }
.status-indicator {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600;
  padding: 4px 12px;
  border-radius: 99px;
  border: 1px solid transparent;
  transition: all 0.3s ease;
}
.status-indicator.ok {
  color: #2dd4a0;
  background: rgba(45,212,160,0.1);
  border-color: rgba(45,212,160,0.2);
}
.status-indicator.err {
  color: #f06b6b;
  background: rgba(240,107,107,0.1);
  border-color: rgba(240,107,107,0.2);
}
.status-indicator:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.status-dot-sm { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.05);
  text-align: right;
}
.status-last-updated {
  font-size: 11px;
  color: rgba(255,255,255,0.25);
  font-weight: 500;
}

/* Transitions */
.slide-up-enter-active { transition: all 0.4s cubic-bezier(0.4,0,0.2,1); }
.slide-up-leave-active { transition: all 0.3s ease; }
.slide-up-enter-from { opacity: 0; transform: translateY(20px); }
.slide-up-leave-to { opacity: 0; transform: translateY(-10px); }

/* ── Animations ── */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .bento-stats { grid-template-columns: repeat(2, 1fr); }
  .bento-main { grid-template-columns: 1fr; }
  .hero-title { font-size: 36px; }
}

@media (max-width: 768px) {
  .hero-title { font-size: 28px; }
  .hero-subtitle { font-size: 14px; }
  .search-bar {
    padding: 12px 16px;
    max-width: 100%;
  }
  .bento-stats {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  .bento-card {
    padding: 16px;
  }
  .actions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
