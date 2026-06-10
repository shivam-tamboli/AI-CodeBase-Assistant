import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [username, setUsername] = useState(localStorage.getItem('username') || '')
  const [isRegistering, setIsRegistering] = useState(false)
  const [authUsername, setAuthUsername] = useState('')
  const [authPassword, setAuthPassword] = useState('')

  // Repository state
  const [repositories, setRepositories] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')

  // Session state
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [chatHistory, setChatHistory] = useState([])

  // Upload state — separate loading per operation
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null) // {type: 'loading'|'success'|'error', text}

  // Reindex state
  const [reindexFile, setReindexFile] = useState(null)
  const [reindexLoading, setReindexLoading] = useState(false)
  const [reindexStatus, setReindexStatus] = useState(null)

  // GitHub import state
  const [githubUrl, setGithubUrl] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [importStatus, setImportStatus] = useState(null)

  // Chat state
  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // Toast notifications
  const [toasts, setToasts] = useState([])

  // File input refs — needed to reset native input value so same file can be re-selected
  const uploadInputRef = useRef(null)
  const importInputRef = useRef(null)  // unused but consistent
  const reindexInputRef = useRef(null)

  // Auto-scroll ref
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  // Intercept 401 responses globally — clears expired token and returns to login
  // Auth endpoints (/auth/login, /auth/register) are excluded — their 401s mean
  // wrong credentials, not an expired session, and are handled in their own catch blocks.
  useEffect(() => {
    const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']
    const id = axios.interceptors.response.use(
      (res) => res,
      (err) => {
        const url = err.config?.url || ''
        const isAuthEndpoint = AUTH_PATHS.some(p => url.includes(p))
        if (err.response?.status === 401 && !isAuthEndpoint) {
          setToken('')
          setUsername('')
          localStorage.removeItem('token')
          localStorage.removeItem('username')
          setRepositories([])
          setSessions([])
          setActiveSessionId(null)
          setChatHistory([])
          setSelectedRepo('')
          showToast('Session expired — please sign in again', 'error')
        }
        return Promise.reject(err)
      }
    )
    return () => axios.interceptors.response.eject(id)
  }, [])

  // Load repos on mount if already logged in (fixes page-refresh bug)
  useEffect(() => {
    if (token) fetchRepositories(token)
  }, [])

  // Load sessions when selected repo changes
  useEffect(() => {
    if (token && selectedRepo) {
      fetchSessions(selectedRepo)
      setActiveSessionId(null)
      setChatHistory([])
    } else {
      setSessions([])
      setActiveSessionId(null)
      setChatHistory([])
    }
  }, [selectedRepo])

  // ── Toasts ────────────────────────────────────────────────────────────────

  const showToast = (message, type = 'info') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500)
  }

  const dismissToast = (id) => setToasts(prev => prev.filter(t => t.id !== id))

  // ── Status Polling ────────────────────────────────────────────────────────

  const pollRepoStatus = (repoId, setStatus, authToken) => {
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${API_URL}/repositories/${repoId}/status`, {
          headers: { Authorization: `Bearer ${authToken}` }
        })
        const { status, name, error } = res.data
        if (status === 'indexed') {
          clearInterval(interval)
          setStatus({ type: 'success', text: `"${name}" indexed successfully` })
          fetchRepositories(authToken)
          setTimeout(() => setStatus(null), 4000)
        } else if (status === 'failed') {
          clearInterval(interval)
          setStatus({ type: 'error', text: `Indexing failed: ${error || 'unknown error'}` })
          setTimeout(() => setStatus(null), 6000)
        } else if (status === 'indexing') {
          setStatus({ type: 'loading', text: 'Indexing code...' })
        }
      } catch {
        clearInterval(interval)
      }
    }, 2000)
  }

  // ── Auth ──────────────────────────────────────────────────────────────────

  const login = async () => {
    try {
      const res = await axios.post(`${API_URL}/auth/login`, { username: authUsername, password: authPassword })
      const newToken = res.data.access_token
      setToken(newToken)
      setUsername(authUsername)
      localStorage.setItem('token', newToken)
      localStorage.setItem('username', authUsername)
      fetchRepositories(newToken)
    } catch (err) {
      showToast('Login failed: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const register = async () => {
    try {
      const res = await axios.post(`${API_URL}/auth/register`, { username: authUsername, password: authPassword })
      const newToken = res.data.access_token
      setToken(newToken)
      setUsername(authUsername)
      localStorage.setItem('token', newToken)
      localStorage.setItem('username', authUsername)
      fetchRepositories(newToken)
    } catch (err) {
      showToast('Registration failed: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const logout = () => {
    setToken('')
    setUsername('')
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setRepositories([])
    setSessions([])
    setActiveSessionId(null)
    setChatHistory([])
    setSelectedRepo('')
  }

  // ── Repositories ──────────────────────────────────────────────────────────

  const fetchRepositories = async (authToken) => {
    try {
      const res = await axios.get(`${API_URL}/repositories`, {
        headers: { Authorization: `Bearer ${authToken}` }
      })
      setRepositories(res.data)
    } catch (err) {
      console.error('Failed to fetch repositories:', err)
    }
  }

  const handleUpload = async () => {
    if (!uploadFile) return
    setUploadLoading(true)
    setUploadStatus({ type: 'loading', text: 'Uploading...' })
    const formData = new FormData()
    formData.append('file', uploadFile)
    try {
      const res = await axios.post(`${API_URL}/repositories/upload`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      })
      const repoId = res.data.id
      // Clear file state and native input so same file can be re-selected
      setUploadFile(null)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
      setUploadStatus({ type: 'loading', text: 'Indexing code...' })
      // Show repo in dropdown immediately (as pending) and auto-select it
      await fetchRepositories(token)
      setSelectedRepo(repoId)
      // Continue polling until indexed/failed
      pollRepoStatus(repoId, setUploadStatus, token)
    } catch (err) {
      setUploadStatus({ type: 'error', text: 'Upload failed: ' + (err.response?.data?.detail || err.message) })
      setTimeout(() => setUploadStatus(null), 5000)
    } finally {
      setUploadLoading(false)
    }
  }

  const handleGitHubImport = async () => {
    if (!githubUrl.trim()) return
    setImportLoading(true)
    setImportStatus({ type: 'loading', text: 'Cloning repository...' })
    try {
      const res = await axios.post(
        `${API_URL}/repositories/import`,
        { url: githubUrl.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      const repoId = res.data.id
      setGithubUrl('')
      setImportStatus({ type: 'loading', text: 'Indexing code...' })
      // Show repo in dropdown immediately and auto-select it
      await fetchRepositories(token)
      setSelectedRepo(repoId)
      pollRepoStatus(repoId, setImportStatus, token)
    } catch (err) {
      setImportStatus({ type: 'error', text: 'Import failed: ' + (err.response?.data?.detail || err.message) })
      setTimeout(() => setImportStatus(null), 6000)
    } finally {
      setImportLoading(false)
    }
  }

  const handleReindex = async () => {
    if (!reindexFile || !selectedRepo) return
    setReindexLoading(true)
    setReindexStatus({ type: 'loading', text: 'Uploading...' })
    const formData = new FormData()
    formData.append('file', reindexFile)
    try {
      const res = await axios.post(`${API_URL}/repositories/${selectedRepo}/reindex`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      })
      setReindexFile(null)
      if (reindexInputRef.current) reindexInputRef.current.value = ''
      setReindexStatus({ type: 'loading', text: 'Re-indexing...' })
      pollRepoStatus(res.data.repository_id || selectedRepo, setReindexStatus, token)
    } catch (err) {
      setReindexStatus({ type: 'error', text: 'Failed: ' + (err.response?.data?.detail || err.message) })
      setTimeout(() => setReindexStatus(null), 5000)
    } finally {
      setReindexLoading(false)
    }
  }

  // ── Sessions ──────────────────────────────────────────────────────────────

  const fetchSessions = async (repoId) => {
    try {
      const res = await axios.get(`${API_URL}/chat/sessions`, {
        params: { repository_id: repoId },
        headers: { Authorization: `Bearer ${token}` }
      })
      setSessions(res.data.sessions || [])
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
    }
  }

  const startNewSession = async () => {
    if (!selectedRepo) return
    try {
      const res = await axios.post(
        `${API_URL}/chat/sessions`,
        { repository_id: selectedRepo },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setActiveSessionId(res.data.session_id)
      setChatHistory([])
      fetchSessions(selectedRepo)
    } catch (err) {
      showToast('Failed to create session: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const selectSession = async (sessionId) => {
    setActiveSessionId(sessionId)
    try {
      const res = await axios.get(`${API_URL}/chat/sessions/${sessionId}/history`, {
        params: { limit: 50 },
        headers: { Authorization: `Bearer ${token}` }
      })
      setChatHistory(res.data.messages || [])
    } catch (err) {
      console.error('Failed to load session history:', err)
      setChatHistory([])
    }
  }

  const deleteSession = async (sessionId, e) => {
    e.stopPropagation()
    try {
      await axios.delete(`${API_URL}/chat/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
        setChatHistory([])
      }
      fetchSessions(selectedRepo)
    } catch (err) {
      showToast('Failed to delete session', 'error')
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────

  const askQuestion = async () => {
    if (!question.trim() || !selectedRepo) return

    let sessionId = activeSessionId
    if (!sessionId) {
      try {
        const res = await axios.post(
          `${API_URL}/chat/sessions`,
          { repository_id: selectedRepo },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        sessionId = res.data.session_id
        setActiveSessionId(sessionId)
        fetchSessions(selectedRepo)
      } catch (err) {
        showToast('Could not create session: ' + (err.response?.data?.detail || err.message), 'error')
        return
      }
    }

    const userMessage = question.trim()
    setQuestion('')
    setChatLoading(true)

    setChatHistory(prev => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
      { role: 'assistant', content: '', sources: [], timestamp: new Date().toISOString() }
    ])

    try {
      const response = await fetch(`${API_URL}/chat/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question: userMessage, repository_id: selectedRepo, session_id: sessionId, limit: 5 })
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || response.statusText)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'token' || event.type === 'done') {
              setChatHistory(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: event.answer,
                  sources: event.sources || updated[updated.length - 1].sources
                }
                return updated
              })
            }
            if (event.type === 'done') fetchSessions(selectedRepo)
          } catch { /* malformed SSE line — skip */ }
        }
      }
    } catch (err) {
      setChatHistory(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: 'Error: ' + err.message }
        return updated
      })
    } finally {
      setChatLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      askQuestion()
    }
  }

  const formatTime = (isoString) => {
    if (!isoString) return ''
    const d = new Date(isoString)
    return (
      d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
      ' ' +
      d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    )
  }

  // ── Derived state (computed before render) ────────────────────────────────

  const activeRepo = repositories.find(r => r.id === selectedRepo)
  const repoStatus = activeRepo?.status
  const repoReady = repoStatus === 'indexed'
  const HINTS = [
    'How does authentication work?',
    'Where is the main entry point?',
    'Explain the database schema',
    'How are errors handled?',
  ]

  // ── Auth Screen ───────────────────────────────────────────────────────────

  if (!token) {
    return (
      <>
        <div className="auth-screen">
          <div className="auth-logo">⚡</div>
          <h1 className="auth-title">AI Codebase Assistant</h1>
          <p className="auth-subtitle">Ask questions about your code in plain English</p>
          <div className="auth-card">
            <h2>{isRegistering ? 'Create account' : 'Sign in'}</h2>
            <div className="auth-field">
              <label htmlFor="auth-user">Username</label>
              <input
                id="auth-user"
                className="auth-input"
                type="text"
                placeholder="your-username"
                value={authUsername}
                onChange={(e) => setAuthUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (isRegistering ? register() : login())}
                autoComplete="username"
              />
            </div>
            <div className="auth-field">
              <label htmlFor="auth-pass">Password</label>
              <input
                id="auth-pass"
                className="auth-input"
                type="password"
                placeholder="••••••••"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (isRegistering ? register() : login())}
                autoComplete={isRegistering ? 'new-password' : 'current-password'}
              />
            </div>
            <button
              className="auth-submit"
              onClick={isRegistering ? register : login}
              disabled={!authUsername || !authPassword}
            >
              {isRegistering ? 'Create account' : 'Sign in'}
            </button>
            <div className="auth-toggle">
              {isRegistering ? 'Already have an account?' : "Don't have an account?"}
              <button onClick={() => setIsRegistering(!isRegistering)}>
                {isRegistering ? 'Sign in' : 'Register'}
              </button>
            </div>
          </div>
        </div>
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.type}`} onClick={() => dismissToast(t.id)}>
              {t.message}
            </div>
          ))}
        </div>
      </>
    )
  }

  // ── Main App ──────────────────────────────────────────────────────────────

  return (
    <div className="app">
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`} onClick={() => dismissToast(t.id)}>
            {t.message}
          </div>
        ))}
      </div>

      <header>
        <div className="header-brand">
          <div className="header-logo">⚡</div>
          <h1>AI Codebase Assistant</h1>
        </div>
        <div className="header-right">
          <div className="status-dot" title="Connected" />
          <span className="username-label">{username}</span>
          <button className="logout-btn" onClick={logout}>Logout</button>
        </div>
      </header>

      <main className="main-layout">

        {/* ── SIDEBAR ──────────────────────────────────────────────────── */}
        <aside className="sidebar">

          {/* Upload ZIP */}
          <div className="sidebar-section">
            <div className="section-label">Upload Repository</div>
            <div className="input-group">
              <label className="file-label">
                <span>📁</span>
                <span>{uploadFile ? uploadFile.name : 'Choose ZIP file'}</span>
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept=".zip"
                  onChange={(e) => setUploadFile(e.target.files[0])}
                />
              </label>
              <button
                className="btn btn-primary btn-full"
                onClick={handleUpload}
                disabled={uploadLoading || !uploadFile}
              >
                {uploadLoading ? 'Uploading...' : 'Upload & Index'}
              </button>
              {uploadStatus && (
                <div className={`status-msg ${uploadStatus.type}`}>{uploadStatus.text}</div>
              )}
            </div>
          </div>

          {/* GitHub Import */}
          <div className="sidebar-section">
            <div className="section-label">Import from GitHub</div>
            <div className="input-group">
              <input
                className="text-input"
                type="url"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGitHubImport()}
              />
              <button
                className="btn btn-primary btn-full"
                onClick={handleGitHubImport}
                disabled={importLoading || !githubUrl.trim()}
              >
                {importLoading ? 'Cloning...' : 'Import Repository'}
              </button>
              {importStatus && (
                <div className={`status-msg ${importStatus.type}`}>{importStatus.text}</div>
              )}
            </div>
          </div>

          {/* Repository select */}
          <div className="sidebar-section">
            <div className="section-label">Active Repository</div>
            <select
              className="repo-select"
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
            >
              <option value="">-- Select a repository --</option>
              {repositories.map(repo => (
                <option key={repo.id} value={repo.id}>
                  {repo.name}{repo.status && repo.status !== 'indexed' ? ` (${repo.status}…)` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Re-index (only when repo selected) */}
          {selectedRepo && (
            <div className="sidebar-section">
              <div className="section-label">Re-index Repository</div>
              <div className="input-group">
                <label className="file-label">
                  <span>📁</span>
                  <span>{reindexFile ? reindexFile.name : 'Choose updated ZIP'}</span>
                  <input
                    ref={reindexInputRef}
                    type="file"
                    accept=".zip"
                    onChange={(e) => setReindexFile(e.target.files[0])}
                  />
                </label>
                <button
                  className="btn btn-ghost btn-full"
                  onClick={handleReindex}
                  disabled={reindexLoading || !reindexFile}
                >
                  {reindexLoading ? 'Uploading...' : 'Re-index ZIP'}
                </button>
                {reindexStatus && (
                  <div className={`status-msg ${reindexStatus.type}`}>{reindexStatus.text}</div>
                )}
              </div>
            </div>
          )}

          {/* Conversations */}
          {selectedRepo && (
            <div className="sidebar-section" style={{ flex: 1, overflowY: 'auto' }}>
              <div className="sessions-header">
                <div className="section-label" style={{ margin: 0 }}>Conversations</div>
                <button className="btn btn-new-chat" onClick={startNewSession}>+ New</button>
              </div>
              {sessions.length === 0 ? (
                <p className="no-sessions">No conversations yet</p>
              ) : (
                <ul className="sessions-list">
                  {sessions.map(session => (
                    <li
                      key={session.id}
                      className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
                      onClick={() => selectSession(session.id)}
                    >
                      <div className="session-info">
                        <span className="session-date">{formatTime(session.updated_at || session.created_at)}</span>
                        <span className="session-count">{session.message_count} messages</span>
                      </div>
                      <button
                        className="session-delete-btn"
                        onClick={(e) => deleteSession(session.id, e)}
                        title="Delete conversation"
                      >×</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

        </aside>

        {/* ── CHAT AREA ─────────────────────────────────────────────────── */}
        <section className="chat-section">
          {!selectedRepo ? (
            <div className="empty-state">
              <div className="empty-state-icon">💬</div>
              <h3>Select a repository to start</h3>
              <p>Upload a ZIP or import from GitHub, then select it from the dropdown above.</p>
            </div>
          ) : (
            <>
              {activeSessionId && (
                <div className="session-badge">
                  <div className="badge-dot" />
                  Conversation active · {chatHistory.length} messages
                </div>
              )}

              {!repoReady && repoStatus && (
                <div className="indexing-banner">
                  <div className="thinking-dots">
                    <span /><span /><span />
                  </div>
                  Repository is {repoStatus} — chat will be available once indexing completes
                </div>
              )}

              <div className="chat-messages">
                {chatHistory.length === 0 && (
                  <div className="empty-chat">
                    <div className="empty-chat-icon">💬</div>
                    <p>{repoReady ? 'Ask a question about your codebase' : 'Indexing in progress — questions available shortly'}</p>
                    {repoReady && (
                      <div className="empty-state-hints">
                        {HINTS.map(hint => (
                          <span
                            key={hint}
                            className="hint-chip"
                            onClick={() => setQuestion(hint)}
                          >{hint}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {chatHistory.map((msg, i) => (
                  <div key={i} className={`message message-${msg.role}`}>
                    <div className="message-header">
                      <div className={`avatar avatar-${msg.role}`}>
                        {msg.role === 'user' ? (username[0]?.toUpperCase() || 'U') : 'AI'}
                      </div>
                      <span className="message-role">{msg.role === 'user' ? username : 'Assistant'}</span>
                    </div>
                    <div className="message-content">
                      {msg.role === 'assistant'
                        ? (msg.content
                            ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                            : <span className="thinking">
                                <div className="thinking-dots">
                                  <span /><span /><span />
                                </div>
                              </span>)
                        : msg.content}
                    </div>

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources">
                        <div className="sources-title">
                          📌 Sources ({msg.sources.length} chunks)
                        </div>
                        <ul>
                          {msg.sources.map((src, j) => (
                            <li key={j}>
                              <code>{src.file_path || '(unknown file)'}</code>
                              {src.start_line > 0 && (
                                <span className="source-lines"> L{src.start_line}–{src.end_line}</span>
                              )}
                              {src.name && (
                                <span className="chunk-name"> · {src.chunk_type}: {src.name}</span>
                              )}
                              <span className="score">{src.score?.toFixed(3)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="message-time">{formatTime(msg.timestamp)}</div>
                  </div>
                ))}

                <div ref={chatEndRef} />
              </div>

              <div className="chat-input-area">
                <div className="input-wrapper">
                  <textarea
                    className="chat-textarea"
                    placeholder={repoReady ? 'Ask a question about your code… (Enter to send)' : 'Waiting for indexing to complete…'}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={handleKeyDown}
                    rows={2}
                    disabled={chatLoading || !repoReady}
                  />
                  <button
                    className="send-btn"
                    onClick={askQuestion}
                    disabled={chatLoading || !question.trim() || !repoReady}
                  >
                    {chatLoading ? '...' : 'Send ↑'}
                  </button>
                </div>
                <p className="input-hint">Enter to send · Shift+Enter for new line</p>
              </div>
            </>
          )}
        </section>

      </main>
    </div>
  )
}

export default App
