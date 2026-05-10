<template>
  <div id="app">
    <!-- Aurora background blobs -->
    <div class="aurora-bg" aria-hidden="true">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
      <div class="grid-texture"></div>
      <div class="noise"></div>
    </div>

    <div class="app-layout">
      <!-- Icon sidebar -->
      <aside class="sidebar">
        <div class="sidebar-logo">
          <div class="logo-mark">
            <el-icon><Cpu /></el-icon>
            <span class="logo-text"></span>
          </div>
        </div>

        <nav class="nav-list">
          <button
            v-for="item in navItems"
            :key="item.key"
            class="nav-item"
            :class="{ active: activeMenu === item.key || (item.match && activeMenu.startsWith(item.match)) }"
            @click="handleMenuSelect(item.key)"
            @mouseenter="handleNavHover(item.key)"
            @mouseleave="handleNavLeave"
          >
            <el-icon class="nav-icon">
              <HomeFilled v-if="item.key === 'dashboard'" />
              <ChatDotRound v-else-if="item.key === 'chat'" />
              <FolderOpened v-else-if="item.key === 'kb-categories'" />
              <DataAnalysis v-else-if="item.key === 'kb-collections'" />
              <Monitor v-else-if="item.key === 'devtools'" />
            </el-icon>
            <span
              v-if="activeMenu === item.key || (item.match && activeMenu.startsWith(item.match))"
              class="nav-active-dot"
            ></span>
            <span class="nav-label">{{ item.label }}</span>
          </button>
        </nav>

        <div class="sidebar-bottom">
          <button
            class="nav-item"
            :class="{ active: activeMenu.startsWith('admin') }"
            @click="handleMenuSelect('admin-config')"
          >
            <el-icon class="nav-icon"><Setting /></el-icon>
            <span class="nav-label">系统管理</span>
          </button>
        </div>
      </aside>

      <!-- Main -->
      <div class="main-wrap">
        <!-- Topbar -->
        <header class="topbar">
          <div class="topbar-left">
            <div class="breadcrumb">
              <span class="breadcrumb-item">{{ currentBreadcrumb }}</span>
              <span class="breadcrumb-separator">/</span>
              <span class="breadcrumb-item active">{{ pageTitle }}</span>
            </div>
          </div>
          <div class="topbar-right">
            <div class="user-info">
              <el-icon class="user-icon"><User /></el-icon>
              <span class="username">{{ username }}</span>
              <el-dropdown @command="handleLogout" class="logout-btn">
                <el-icon><ArrowDown /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <div class="model-select-wrap">
              <el-icon class="model-icon"><Cpu /></el-icon>
              <el-select v-model="selectedModel" size="small" style="width:160px" placeholder="模型">
                <el-option v-for="m in availableModels" :key="m.name" :label="m.name" :value="m.name" />
              </el-select>
            </div>
            <div class="status-pill" :class="apiStatus ? 'online' : 'offline'">
              <span class="pulse-dot"></span>
              {{ apiStatus ? 'Connected' : 'Offline' }}
            </div>
          </div>
        </header>

        <!-- Content -->
        <main class="content">
          <div class="content-container">
            <transition name="fade-slide" mode="out-in">
              <div v-if="activeMenu === 'dashboard'" key="dashboard">
                <DashboardView @navigate="handleMenuSelect" />
              </div>
              <div v-else-if="activeMenu === 'chat'" key="chat">
                <SimpleChat :model="selectedModel" />
              </div>
              <div v-else-if="activeMenu === 'kb-categories'" key="categories">
                <CategoryManager />
              </div>
              <div v-else-if="activeMenu === 'kb-collections' || activeMenu.startsWith('admin')" key="admin">
                <AdminPanel :active-tab="adminTab" ref="adminPanelRef" />
              </div>
              <div v-else-if="activeMenu === 'devtools'" key="devtools">
                <DevTools />
              </div>
            </transition>
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiService } from '../services/api'
import { useAuthStore } from '../stores/auth'
import SimpleChat from '../components/SimpleChat.vue'
import CategoryManager from '../components/doc/CategoryManager.vue'
import AdminPanel from '../components/AdminPanel.vue'
import DevTools from '../components/DevTools.vue'
import DashboardView from '../views/DashboardView.vue'
import {
  HomeFilled,
  ChatDotRound,
  FolderOpened,
  DataAnalysis,
  Monitor,
  Setting,
  Cpu,
  ArrowDown,
  User
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const { logout, username } = useAuthStore()
const activeMenu = ref('dashboard')
const selectedModel = ref('qwen-turbo')
const availableModels = ref([])
const apiStatus = ref(false)
const hoveredNav = ref(null)
const adminPanelRef = ref(null)

const navItems = [
  { key: 'dashboard', label: 'Dashboard', icon: 'HomeFilled' },
  { key: 'chat', label: '智能对话', icon: 'ChatDotRound' },
  { key: 'kb-categories', label: '类目管理', icon: 'FolderOpened' },
  { key: 'kb-collections', label: '知识库', icon: 'DataAnalysis' },
  { key: 'devtools', label: '开发工具', icon: 'Monitor' }
]

const adminTabMap = { 'kb-collections': 'collections', 'admin-create': 'create', 'admin-config': 'config' }
const adminTab = computed(() => adminTabMap[activeMenu.value] || 'namespace')

const pageMeta = {
  dashboard: { title: 'Dashboard', sub: 'Enterprise Knowledge Base', breadcrumb: 'Home' },
  chat: { title: '智能对话', sub: 'AI-powered conversation', breadcrumb: 'AI' },
  'kb-categories': { title: '类目管理', sub: 'Document categories', breadcrumb: 'Documents' },
  'kb-collections': { title: '知识库列表', sub: 'Vector collections', breadcrumb: 'Knowledge' },
  'admin-create': { title: '创建知识库', sub: 'New collection', breadcrumb: 'Admin' },
  'admin-config': { title: '配置信息', sub: 'System configuration', breadcrumb: 'Admin' },
  devtools: { title: '开发工具', sub: 'API & debugging', breadcrumb: 'Tools' }
}
const pageTitle = computed(() => pageMeta[activeMenu.value]?.title || '')
const pageSubtitle = computed(() => pageMeta[activeMenu.value]?.sub || '')
const currentBreadcrumb = computed(() => pageMeta[activeMenu.value]?.breadcrumb || 'Home')

const handleMenuSelect = (key) => {
  if (activeMenu.value === key) {
    if (key === 'kb-collections' && adminPanelRef.value) {
      adminPanelRef.value.resetToInitialState()
    } else {
      const tempKey = key + '_temp'
      activeMenu.value = tempKey
      setTimeout(() => {
        activeMenu.value = key
      }, 0)
    }
  } else {
    activeMenu.value = key
  }
}
const handleNavHover = (key) => { hoveredNav.value = key }
const handleNavLeave = () => { hoveredNav.value = null }

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    logout()
    ElMessage.success('已退出登录')
    window.location.href = '/login'
  } catch {
    // User cancelled
  }
}

onMounted(async () => {
  try {
    const res = await apiService.getModels()
    availableModels.value = res.models
    selectedModel.value = res.default_model
    apiStatus.value = true
  } catch {
    availableModels.value = [
      { name: 'qwen-turbo' }, { name: 'qwen-plus' }, { name: 'qwen-max' }
    ]
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0d1117;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-feature-settings: 'rlig' 1, 'calt' 1;
}
</style>

<style scoped>
/* ── Aurora background ── */
.aurora-bg {
  position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none;
}
.blob {
  position: absolute; border-radius: 50%;
  filter: blur(100px); opacity: 0.25;
  animation: drift 20s ease-in-out infinite alternate;
}
.blob-1 {
  width: 700px; height: 700px; top: -250px; left: -150px;
  background: radial-gradient(circle, #4f8ef7 0%, #7c3aed 50%, transparent 100%);
  animation-duration: 22s;
}
.blob-2 {
  width: 600px; height: 600px; bottom: -200px; right: -150px;
  background: radial-gradient(circle, #06b6d4 0%, #34d399 50%, transparent 100%);
  animation-duration: 18s; animation-delay: -8s;
}
.blob-3 {
  width: 520px; height: 520px; top: 35%; left: 45%;
  background: radial-gradient(circle, #a78bfa 0%, #f472b6 50%, transparent 100%);
  animation-duration: 25s; animation-delay: -14s; opacity: 0.2;
}
.grid-texture {
  position: absolute; inset: 0; opacity: 0.03;
  background-image: linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
  background-size: 20px 20px;
}
.noise {
  position: absolute; inset: 0; opacity: 0.02;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  background-size: 200px 200px;
}
@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(40px, -30px) scale(1.05); }
}

/* ── Layout ── */
#app { height: 100vh; overflow: hidden; }
.app-layout {
  position: relative; z-index: 1;
  display: flex; height: 100vh; overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Sidebar ── */
.sidebar {
  width: 200px; flex-shrink: 0;
  display: flex; flex-direction: column;
  background: rgba(13,17,23,0.85);
  backdrop-filter: blur(32px);
  border-right: 1px solid rgba(255,255,255,0.08);
  padding: 0;
  box-shadow: 2px 0 10px rgba(0,0,0,0.2);
}
.sidebar-logo {
  height: 60px; display: flex; align-items: center;
  width: 100%; border-bottom: 1px solid rgba(255,255,255,0.05);
  padding: 0 16px;
}
.logo-mark {
  width: 36px; height: 36px; border-radius: 12px;
  background: linear-gradient(135deg, #3b6fd4, #5b4fcf);
  display: flex; align-items: center; gap: 8px;
  font-size: 16px; color: white;
  box-shadow: 0 4px 16px rgba(59,111,212,0.6);
  padding: 0 12px;
  transition: all 0.3s ease;
}
.logo-mark:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(59,111,212,0.8);
}
.logo-text {
  font-weight: 700;
  font-size: 14px;
  opacity: 1;
  transform: translateX(0);
  transition: all 0.3s ease;
}
.nav-list {
  flex: 1; display: flex; flex-direction: column;
  align-items: stretch; padding: 16px 0; gap: 8px; width: 100%;
}
.nav-item {
  position: relative;
  height: 44px; border-radius: 12px;
  display: flex; align-items: center;
  cursor: pointer; color: rgba(255,255,255,0.4); font-size: 18px;
  background: transparent; border: none; outline: none;
  transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
  padding: 0 16px;
  width: 100%;
  justify-content: flex-start;
}
.nav-icon {
  transition: all 0.3s ease;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.nav-item:hover {
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.8);
  transform: translateX(4px);
}
.nav-item.active {
  background: rgba(79,142,247,0.15);
  color: #7eb3ff;
  box-shadow: 0 0 0 1px rgba(79,142,247,0.3);
  transform: translateX(8px);
}
.nav-item.active .nav-icon {
  transform: scale(1.1);
}
.nav-active-dot {
  position: absolute; right: -1px; top: 50%; transform: translateY(-50%);
  width: 3px; height: 18px; border-radius: 99px;
  background: linear-gradient(180deg, #7eb3ff, #a78bfa);
  box-shadow: 0 0 10px rgba(79,142,247,0.8);
  transition: all 0.3s ease;
}
.nav-label {
  font-size: 14px;
  font-weight: 500;
  opacity: 1;
  transform: translateX(0);
  transition: all 0.3s ease;
  white-space: nowrap;
  margin-left: 12px;
}
.sidebar-bottom {
  padding: 16px 0; border-top: 1px solid rgba(255,255,255,0.05);
  width: 100%;
}

/* ── Main wrap ── */
.main-wrap {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
  background: rgba(13,17,23,0.6);
  backdrop-filter: blur(20px);
}

/* ── Topbar ── */
.topbar {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px;
  background: rgba(13,17,23,0.75);
  backdrop-filter: blur(32px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.topbar-left {
  display: flex; align-items: center;
}
.topbar-right {
  display: flex; align-items: center; gap: 16px;
}
.user-info {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px;
  border-radius: 99px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}
.user-icon {
  color: rgba(255,255,255,0.4);
}
.username {
  color: rgba(255,255,255,0.7);
  font-size: 14px;
}
.logout-btn {
  color: rgba(255,255,255,0.4);
  cursor: pointer;
  transition: color 0.3s ease;
}
.logout-btn:hover {
  color: #7eb3ff;
}
.breadcrumb {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px;
}
.breadcrumb-item {
  color: rgba(255,255,255,0.5);
  transition: color 0.3s ease;
}
.breadcrumb-item:hover {
  color: rgba(255,255,255,0.8);
}
.breadcrumb-item.active {
  color: #f0f4ff;
  font-weight: 600;
}
.breadcrumb-separator {
  color: rgba(255,255,255,0.2);
  font-size: 12px;
}
.page-title {
  font-size: 18px; font-weight: 700; color: #f0f4ff; letter-spacing: -0.2px;
  margin-bottom: 2px;
}
.page-subtitle {
  font-size: 12px; color: rgba(255,255,255,0.3);
  margin-top: 2px;
}
.model-select-wrap {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  transition: all 0.3s ease;
}
.model-select-wrap:hover {
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.12);
}
.model-icon {
  color: rgba(255,255,255,0.4); font-size: 16px;
  transition: color 0.3s ease;
}
.model-select-wrap:hover .model-icon {
  color: rgba(255,255,255,0.8);
}

.status-pill {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: 99px;
  font-size: 12px; font-weight: 500; letter-spacing: 0.3px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: rgba(255,255,255,0.4);
  transition: all 0.3s ease;
}
.status-pill:hover {
  background: rgba(255,255,255,0.08);
}
.status-pill.online {
  color: #2dd4a0; border-color: rgba(45,212,160,0.3);
  background: rgba(45,212,160,0.08);
}
.status-pill.online:hover {
  background: rgba(45,212,160,0.12);
}
.pulse-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: rgba(255,255,255,0.4);
  transition: all 0.3s ease;
}
.status-pill.online .pulse-dot {
  background: #2dd4a0;
  box-shadow: 0 0 0 0 rgba(45,212,160,0.4);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  from { box-shadow: 0 0 0 0 rgba(45,212,160,0.4); }
  70% { box-shadow: 0 0 0 8px rgba(45,212,160,0); }
  to { box-shadow: 0 0 0 0 rgba(45,212,160,0); }
}

/* ── Content ── */
.content {
  flex: 1; overflow-y: auto; padding: 32px 36px;
  background: transparent;
}
.content-container {
  max-width: 1400px;
  margin: 0 auto;
  animation: fadeInUp 0.5s ease-out;
}
.content::-webkit-scrollbar {
  width: 6px;
}
.content::-webkit-scrollbar-track {
  background: rgba(255,255,255,0.03);
  border-radius: 99px;
}
.content::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 99px;
  transition: background 0.3s ease;
}
.content::-webkit-scrollbar-thumb:hover {
  background: rgba(255,255,255,0.2);
}

/* ── Animations ── */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .sidebar { width: 56px; }
  .sidebar:hover { width: 160px; }
  .topbar { padding: 0 16px; }
  .content { padding: 20px 16px; }
  .topbar-right { gap: 8px; }
  .model-select-wrap { padding: 4px 8px; }
  .status-pill { padding: 4px 8px; font-size: 11px; }
}

@media (max-width: 480px) {
  .sidebar { width: 52px; }
  .logo-mark { width: 32px; height: 32px; padding: 0; }
  .nav-item { width: 40px; height: 40px; }
  .topbar { height: 56px; }
  .breadcrumb { font-size: 12px; }
  .page-title { font-size: 16px; }
}
</style>
