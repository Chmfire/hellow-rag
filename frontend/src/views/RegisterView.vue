<template>
  <div class="auth-container">
    <div class="aurora-bg" aria-hidden="true">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
      <div class="grid-texture"></div>
      <div class="noise"></div>
    </div>

    <div class="auth-card">
      <div class="auth-header">
        <div class="logo-mark">
          <el-icon :size="32"><Cpu /></el-icon>
        </div>
        <h1>创建账号</h1>
        <p>注册一个新账号开始使用</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="auth-form"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="User"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item prop="role">
          <el-select v-model="form.role" placeholder="选择角色" size="large" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.role === 'admin'" prop="adminCode">
          <el-input
            v-model="form.adminCode"
            type="password"
            placeholder="管理员邀请码"
            size="large"
            :prefix-icon="Key"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="auth-button"
            :loading="isLoading"
            @click="handleRegister"
          >
            注册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        <span>已有账号？</span>
        <router-link to="/login" class="auth-link">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Cpu, User, Lock, Key } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const { register, isLoading } = useAuthStore()
const formRef = ref(null)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role: 'user',
  adminCode: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度在 3 到 32 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

async function handleRegister() {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      await register(
        form.username,
        form.password,
        form.role,
        form.role === 'admin' ? form.adminCode : null
      )
      ElMessage.success('注册成功')
      router.push('/')
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '注册失败，请稍后重试')
    }
  })
}
</script>

<style scoped>
.auth-container {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0d1117;
  overflow: hidden;
  padding: 40px 20px;
}

.aurora-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.25;
  animation: drift 20s ease-in-out infinite alternate;
}

.blob-1 {
  width: 700px;
  height: 700px;
  top: -250px;
  left: -150px;
  background: radial-gradient(circle, #4f8ef7 0%, #7c3aed 50%, transparent 100%);
  animation-duration: 22s;
}

.blob-2 {
  width: 600px;
  height: 600px;
  bottom: -200px;
  right: -150px;
  background: radial-gradient(circle, #06b6d4 0%, #34d399 50%, transparent 100%);
  animation-duration: 18s;
  animation-delay: -8s;
}

.blob-3 {
  width: 520px;
  height: 520px;
  top: 35%;
  left: 45%;
  background: radial-gradient(circle, #a78bfa 0%, #f472b6 50%, transparent 100%);
  animation-duration: 25s;
  animation-delay: -14s;
  opacity: 0.2;
}

.grid-texture {
  position: absolute;
  inset: 0;
  opacity: 0.03;
  background-image: linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
  background-size: 20px 20px;
}

.noise {
  position: absolute;
  inset: 0;
  opacity: 0.02;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  background-size: 200px 200px;
}

@keyframes drift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(40px, -30px) scale(1.05); }
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 48px 40px;
  background: rgba(13, 17, 23, 0.85);
  backdrop-filter: blur(32px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 24px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
}

.auth-header {
  text-align: center;
  margin-bottom: 36px;
}

.logo-mark {
  width: 64px;
  height: 64px;
  margin: 0 auto 24px;
  border-radius: 20px;
  background: linear-gradient(135deg, #3b6fd4, #5b4fcf);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 32px rgba(59, 111, 212, 0.5);
}

.auth-header h1 {
  color: #f0f4ff;
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
}

.auth-header p {
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  margin: 0;
}

.auth-form {
  margin-bottom: 24px;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.auth-form :deep(.el-input__wrapper),
.auth-form :deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: none;
  padding: 8px 16px;
  transition: all 0.3s ease;
}

.auth-form :deep(.el-input__wrapper:hover),
.auth-form :deep(.el-select__wrapper:hover) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
}

.auth-form :deep(.el-input__wrapper.is-focus),
.auth-form :deep(.el-select__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.08);
  border-color: #4f8ef7;
  box-shadow: 0 0 0 3px rgba(79, 142, 247, 0.2);
}

.auth-form :deep(.el-input__inner),
.auth-form :deep(.el-select__placeholder) {
  color: #f0f4ff;
}

.auth-form :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

.auth-form :deep(.el-input__prefix),
.auth-form :deep(.el-select__icon) {
  color: rgba(255, 255, 255, 0.4);
}

.auth-form :deep(.el-select__wrapper .el-select__placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

.auth-form :deep(.el-select__wrapper .el-select__selected-item) {
  color: #f0f4ff;
}

.auth-form :deep(.el-select-dropdown) {
  background: rgba(20, 24, 32, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}

.auth-form :deep(.el-select-dropdown__item) {
  color: rgba(255, 255, 255, 0.7);
}

.auth-form :deep(.el-select-dropdown__item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #f0f4ff;
}

.auth-form :deep(.el-select-dropdown__item.selected) {
  color: #4f8ef7;
  background: rgba(79, 142, 247, 0.1);
}

.auth-button {
  width: 100%;
  height: 48px;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #4f8ef7, #5b4fcf);
  border: none;
  box-shadow: 0 8px 24px rgba(79, 142, 247, 0.4);
  transition: all 0.3s ease;
}

.auth-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(79, 142, 247, 0.5);
}

.auth-button:active {
  transform: translateY(0);
}

.auth-footer {
  text-align: center;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
}

.auth-link {
  color: #4f8ef7;
  text-decoration: none;
  font-weight: 600;
  margin-left: 4px;
  transition: color 0.3s ease;
}

.auth-link:hover {
  color: #7eb3ff;
}
</style>
