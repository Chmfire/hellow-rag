import { ref, computed } from 'vue'
import { apiService } from '../services/api'

// Reactive state
const user = ref(null)
const isAuthenticated = ref(false)
const isLoading = ref(false)

// Initialize from localStorage
function initAuth() {
  const storedUser = apiService.getStoredUser()
  const hasToken = apiService.isAuthenticated()
  if (storedUser && hasToken) {
    user.value = storedUser
    isAuthenticated.value = true
  }
}

// Login
async function login(username, password) {
  isLoading.value = true
  try {
    const response = await apiService.login(username, password)
    user.value = { username: response.username, role: response.role }
    isAuthenticated.value = true
    return response
  } finally {
    isLoading.value = false
  }
}

// Register
async function register(username, password, role = 'user', adminCode = null) {
  isLoading.value = true
  try {
    const response = await apiService.register(username, password, role, adminCode)
    user.value = { username: response.username, role: response.role }
    isAuthenticated.value = true
    return response
  } finally {
    isLoading.value = false
  }
}

// Logout
function logout() {
  apiService.logout()
  user.value = null
  isAuthenticated.value = false
}

// Check if user has admin role
const isAdmin = computed(() => user.value?.role === 'admin')

// Username
const username = computed(() => user.value?.username || '')

// Listen for auth events
if (typeof window !== 'undefined') {
  window.addEventListener('auth-login', (event) => {
    user.value = event.detail
    isAuthenticated.value = true
  })

  window.addEventListener('auth-logout', () => {
    user.value = null
    isAuthenticated.value = false
  })
}

// Initialize
initAuth()

export const useAuthStore = () => ({
  user,
  isAuthenticated,
  isLoading,
  isAdmin,
  username,
  login,
  register,
  logout,
  initAuth
})
