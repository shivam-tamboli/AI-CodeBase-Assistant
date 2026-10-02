import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Session storage ─────────────────────────────────────────────────────────
// localStorage is the single source of truth for the access token, so the
// request interceptor always sends the latest one — including right after
// login or a refresh, before React state has caught up.

export const getToken = () => localStorage.getItem('token') || ''
export const getStoredUsername = () => localStorage.getItem('username') || ''

export const saveSession = (token, username) => {
  localStorage.setItem('token', token)
  if (username !== undefined) localStorage.setItem('username', username)
}

export const clearSession = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
}

// ── Client ──────────────────────────────────────────────────────────────────

// withCredentials so the httpOnly refresh-token cookie rides along on /auth/*.
const api = axios.create({ baseURL: API_URL, withCredentials: true })

// /auth/* runs on credentials or the refresh cookie, never the access token,
// so a stale token isn't sent there.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token && !config.url.startsWith('/auth/')) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Best human-readable message from an API error. HTTPExceptions use `detail`;
// validation (422) and rate-limit (429) errors use the `error` envelope.
export const apiError = (err) => {
  const data = err.response?.data
  const field = data?.error?.details?.errors?.[0]?.message
  return data?.detail || field?.replace(/^Value error, /, '') || data?.error?.message || err.message
}

// Intercept 401 responses — attempt silent token refresh before giving up.
// Auth endpoints are excluded: their 401s mean wrong credentials, not expiry.
// Returns an uninstall function so App can tie it to its lifecycle.
export const installAuthRefresh = ({ onRefreshed, onExpired }) => {
  const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']
  let isRefreshing = false
  let queue = []

  const processQueue = (error) => {
    queue.forEach(({ resolve, reject }) => error ? reject(error) : resolve())
    queue = []
  }

  const id = api.interceptors.response.use(
    (res) => res,
    async (err) => {
      const original = err.config
      const url = original?.url || ''
      const isAuthEndpoint = AUTH_PATHS.some(p => url.includes(p))

      if (err.response?.status !== 401 || isAuthEndpoint || original._retry) {
        return Promise.reject(err)
      }

      // The request interceptor re-reads the stored token, so a retry
      // automatically carries the refreshed one.
      if (isRefreshing) {
        return new Promise((resolve, reject) => queue.push({ resolve, reject }))
          .then(() => api(original))
      }

      original._retry = true
      isRefreshing = true

      try {
        const res = await api.post('/auth/refresh')
        const newToken = res.data.access_token
        saveSession(newToken)
        onRefreshed(newToken)
        processQueue(null)
        return api(original)
      } catch {
        processQueue(new Error('Refresh failed'))
        clearSession()
        onExpired()
        return Promise.reject(err)
      } finally {
        isRefreshing = false
      }
    }
  )
  return () => api.interceptors.response.eject(id)
}

// ── Auth ────────────────────────────────────────────────────────────────────

export const login = (username, password) =>
  api.post('/auth/login', { username, password }).then(r => r.data.access_token)

export const register = (username, password) =>
  api.post('/auth/register', { username, password }).then(r => r.data.access_token)

export const logout = () => api.post('/auth/logout')

// Plain fetch on purpose: no credentials/headers means no CORS preflight, and
// it stays clear of the 401 interceptor. Used to start a Render cold start
// (~50s) while the user is still on the login page. Failures don't matter.
export const pingHealth = () => fetch(`${API_URL}/health`).catch(() => {})

// ── Repositories ────────────────────────────────────────────────────────────

export const listRepositories = () => api.get('/repositories').then(r => r.data)

export const getRepositoryStatus = (repoId) =>
  api.get(`/repositories/${repoId}/status`).then(r => r.data)

const zipForm = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return formData
}
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

export const uploadRepository = (file) =>
  api.post('/repositories/upload', zipForm(file), multipart).then(r => r.data)

export const reindexRepository = (repoId, file) =>
  api.post(`/repositories/${repoId}/reindex`, zipForm(file), multipart).then(r => r.data)

// githubToken is only sent when the user supplies one (private repos); it's never stored.
export const importRepository = (url, githubToken) =>
  api.post('/repositories/import', { url, ...(githubToken && { github_token: githubToken }) })
    .then(r => r.data)

// ── Chat sessions ───────────────────────────────────────────────────────────

export const listSessions = (repoId) =>
  api.get('/chat/sessions', { params: { repository_id: repoId } }).then(r => r.data.sessions || [])

export const createSession = (repoId) =>
  api.post('/chat/sessions', { repository_id: repoId }).then(r => r.data.session_id)

export const getSessionHistory = (sessionId, limit = 50) =>
  api.get(`/chat/sessions/${sessionId}/history`, { params: { limit } }).then(r => r.data.messages || [])

export const deleteSession = (sessionId) => api.delete(`/chat/sessions/${sessionId}`)

// SSE needs a streaming body, which axios doesn't expose in the browser, so
// this one uses fetch and attaches the token itself.
export const streamQuery = (body) =>
  fetch(`${API_URL}/chat/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify(body),
  })
