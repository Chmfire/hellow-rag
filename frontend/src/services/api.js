import axios from 'axios'

// Token storage
const TOKEN_KEY = 'rag_auth_token'
const USER_KEY = 'rag_user_info'

// Create axios instance
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url, config.data)
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    console.error('Request Error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.data)
    return response
  },
  (error) => {
    console.error('Response Error:', error.response?.status, error.response?.data || error.message)
    // If 401 Unauthorized, clear token and redirect to login
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      window.dispatchEvent(new CustomEvent('auth-logout'))
    }
    return Promise.reject(error)
  }
)

// API service methods
export const apiService = {
  // ==================== Auth methods ====================
  async login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    const { access_token, username: user, role } = response.data
    localStorage.setItem(TOKEN_KEY, access_token)
    localStorage.setItem(USER_KEY, JSON.stringify({ username: user, role }))
    window.dispatchEvent(new CustomEvent('auth-login', { detail: { username: user, role } }))
    return response.data
  },

  async register(username, password, role = 'user', adminCode = null) {
    const payload = { username, password, role }
    if (adminCode) payload.admin_code = adminCode
    const response = await api.post('/auth/register', payload)
    const { access_token, username: user, role: userRole } = response.data
    localStorage.setItem(TOKEN_KEY, access_token)
    localStorage.setItem(USER_KEY, JSON.stringify({ username: user, role: userRole }))
    window.dispatchEvent(new CustomEvent('auth-login', { detail: { username: user, role: userRole } }))
    return response.data
  },

  async getCurrentUser() {
    const response = await api.get('/auth/me')
    return response.data
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    window.dispatchEvent(new CustomEvent('auth-logout'))
  },

  isAuthenticated() {
    return !!localStorage.getItem(TOKEN_KEY)
  },

  getStoredUser() {
    const userStr = localStorage.getItem(USER_KEY)
    return userStr ? JSON.parse(userStr) : null
  },

  getToken() {
    return localStorage.getItem(TOKEN_KEY)
  },

  // ==================== Other methods ====================
  // Health check
  async healthCheck() {
    const response = await api.get('/health')
    return response.data
  },

  // Get available models
  async getModels() {
    const response = await api.get('/models')
    return response.data
  },

  // Chat with agent
  async chat(messages, model = null, temperature = null) {
    const payload = { messages }
    if (model) payload.model = model
    if (temperature !== null) payload.temperature = temperature
    
    const response = await api.post('/chat', payload)  // 对应 /api/v1/chat
    return response.data
  },

  // Knowledge base query
  async knowledgeQuery(query, sessionId = 'default', model = null, collection = null, forceMultiDoc = null, keywordFilter = null, queryImage = null) {
    const payload = { query, session_id: sessionId }
    if (model) payload.model = model
    if (collection) payload.collection = collection
    if (forceMultiDoc != null) payload.force_multi_doc = forceMultiDoc
    if (keywordFilter) payload.keyword_filter = keywordFilter
    if (queryImage) payload.query_image = queryImage

    const response = await api.post('/knowledge', payload)
    return response.data
  },

  /**
   * Knowledge SSE（POST /knowledge/stream）。handlers: { onMeta, onDelta, onDone, onError }，均为可选。
   */
  async knowledgeQueryStream(payload, handlers = {}, signal = undefined) {
    const body = {
      query: payload.query,
      session_id: payload.session_id ?? 'default',
      ...(payload.model && { model: payload.model }),
      ...(payload.collection != null && { collection: payload.collection }),
      ...(payload.force_multi_doc != null && { force_multi_doc: payload.force_multi_doc }),
      ...(payload.keyword_filter && { keyword_filter: payload.keyword_filter }),
      ...(payload.query_image && { query_image: payload.query_image }),
    }
    const res = await fetch('/api/v1/knowledge/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        // 避免中间层对响应做 gzip，导致整段缓冲后才解压、前端收不到增量
        'Accept-Encoding': 'identity',
      },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok) {
      const err = new Error(`stream HTTP ${res.status}`)
      handlers.onError?.(err)
      throw err
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')

    const normalizeLf = (s) => s.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

    const dispatchSseBlock = (blockRaw) => {
      const block = blockRaw.trim()
      if (!block) return
      let ev = null
      let dataStr = null
      for (const line of block.split('\n')) {
        const L = line.trimEnd()
        if (L.startsWith('event:')) ev = L.slice(6).trim()
        else if (L.startsWith('data:')) dataStr = L.slice(5).trim()
      }
      if (dataStr == null) return
      let data
      try {
        data = JSON.parse(dataStr)
      } catch (e) {
        handlers.onError?.(e)
        return
      }
      if (ev === 'meta') handlers.onMeta?.(data)
      else if (ev === 'delta') handlers.onDelta?.(data)
      else if (ev === 'done') handlers.onDone?.(data)
      else if (ev === 'thinking') handlers.onThinking?.(data)
      else if (ev === 'stopped') handlers.onStopped?.(data)
      else if (ev === 'error') handlers.onError?.(new Error(data.message || 'stream error'))
    }

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (value) buffer += decoder.decode(value, { stream: !done })
      if (done) {
        buffer += decoder.decode()
        buffer = normalizeLf(buffer)
        let sep
        while ((sep = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          dispatchSseBlock(block)
        }
        if (buffer.trim()) dispatchSseBlock(buffer)
        break
      }
      buffer = normalizeLf(buffer)
      let sep
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        dispatchSseBlock(block)
      }
    }
  },

  /**
   * 获取流式生成进度（用于断点续传）
   */
  async getStreamResume(sessionId) {
    const res = await fetch(`/api/v1/knowledge/resume/${sessionId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) {
      throw new Error(`resume HTTP ${res.status}`)
    }
    return await res.json()
  },

  // Knowledge base QA (alias for better naming)
  async knowledgeQA(query, model = null, sessionId = 'default', collection = null, forceMultiDoc = null, keywordFilter = null, queryImage = null) {
    return this.knowledgeQuery(query, sessionId, model, collection, forceMultiDoc, keywordFilter, queryImage)
  },

  // Generic API call for testing
  async genericCall(method, endpoint, data = null) {
    const config = { method, url: endpoint }
    if (data) config.data = data
    
    const response = await api(config)
    return response.data
  },

  // 停止正在进行的问答
  async stopKnowledgeQA(sessionId) {
    const response = await api.post('/knowledge/stop', null, {
      params: { session_id: sessionId }
    })
    return response.data
  }
}

export default api