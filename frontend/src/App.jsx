import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

axios.defaults.withCredentials = true

function AuthStoryPanel() {
  const [phase, setPhase] = React.useState(0)
  const [visible, setVisible] = React.useState(false)
  const [progress, setProgress] = React.useState(0)
  const [pipelineStep, setPipelineStep] = React.useState(0)
  const [simQuestion, setSimQuestion] = React.useState('')
  const [simAnswer, setSimAnswer] = React.useState('')
  const [simAnswerVisible, setSimAnswerVisible] = React.useState(false)
  const [simSourceVisible, setSimSourceVisible] = React.useState(false)
  const [explorerRows, setExplorerRows] = React.useState([])
  const [explorerHighlight, setExplorerHighlight] = React.useState(null)
  const [explorerSearch, setExplorerSearch] = React.useState(null)
  const [explorerBadge, setExplorerBadge] = React.useState(null)

  const PHASE_DURATION = [5000, 6000, 5500, 4500]
  const PHASES = ['RAG Pipeline', 'Live Query', 'Codebase Explorer', 'API Usage']

  const QUESTION_TEXT = 'How does authentication work?'
  const ANSWER_TEXT = 'Authentication uses JWT tokens. The AuthService validates credentials, generates a signed token, and attaches it to every request via middleware.'

  const EXPLORER_ITEMS = [
    { id: 0, indent: '', icon: '📁', name: 'src/', type: 'folder' },
    { id: 1, indent: 'indent-1', icon: '📁', name: 'auth/', type: 'folder' },
    { id: 2, indent: 'indent-2', icon: '🐍', name: 'auth_service.py', type: 'file', badge: '41 chunks' },
    { id: 3, indent: 'indent-2', icon: '🐍', name: 'jwt_handler.py', type: 'file', badge: '28 chunks' },
    { id: 4, indent: 'indent-1', icon: '📁', name: 'routes/', type: 'folder' },
    { id: 5, indent: 'indent-2', icon: '🐍', name: 'query.py', type: 'file' },
    { id: 6, indent: 'indent-2', icon: '🐍', name: 'repository.py', type: 'file' },
  ]

  const resetPhaseState = () => {
    setPipelineStep(0)
    setSimQuestion('')
    setSimAnswer('')
    setSimAnswerVisible(false)
    setSimSourceVisible(false)
    setExplorerRows([])
    setExplorerHighlight(null)
    setExplorerSearch(null)
    setExplorerBadge(null)
  }

  React.useEffect(() => {
    const timers = []
    setVisible(false)
    setProgress(0)
    resetPhaseState()

    timers.push(setTimeout(() => setVisible(true), 100))

    const duration = PHASE_DURATION[phase]
    const startTime = Date.now()
    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime
      const pct = Math.min((elapsed / duration) * 100, 100)
      setProgress(pct)
    }, 50)
    timers.push(progressInterval)

    // Phase 0 — Pipeline
    if (phase === 0) {
      for (let i = 0; i <= 6; i++) {
        timers.push(setTimeout(() => setPipelineStep(i), 400 + i * 600))
      }
    }

    // Phase 1 — Query simulation
    if (phase === 1) {
      let q = ''
      QUESTION_TEXT.split('').forEach((char, i) => {
        timers.push(setTimeout(() => {
          q += char
          setSimQuestion(q)
        }, 300 + i * 45))
      })
      const afterQ = 300 + QUESTION_TEXT.length * 45 + 400
      timers.push(setTimeout(() => setSimAnswerVisible(true), afterQ))
      let a = ''
      ANSWER_TEXT.split('').forEach((char, i) => {
        timers.push(setTimeout(() => {
          a += char
          setSimAnswer(a)
        }, afterQ + 200 + i * 18))
      })
      const afterA = afterQ + 200 + ANSWER_TEXT.length * 18 + 300
      timers.push(setTimeout(() => setSimSourceVisible(true), afterA))
    }

    // Phase 2 — Explorer
    if (phase === 2) {
      EXPLORER_ITEMS.forEach((item, i) => {
        timers.push(setTimeout(() => {
          setExplorerRows(prev => [...prev, item.id])
        }, 300 + i * 280))
      })
      timers.push(setTimeout(() => setExplorerHighlight(2), 300 + EXPLORER_ITEMS.length * 280 + 200))
      timers.push(setTimeout(() => setExplorerSearch(2), 300 + EXPLORER_ITEMS.length * 280 + 600))
      timers.push(setTimeout(() => {
        setExplorerSearch(3)
        setExplorerHighlight(3)
      }, 300 + EXPLORER_ITEMS.length * 280 + 1400))
      timers.push(setTimeout(() => setExplorerBadge(3), 300 + EXPLORER_ITEMS.length * 280 + 1800))
    }

    // Advance to next phase
    const nextTimer = setTimeout(() => {
      setVisible(false)
      setTimeout(() => {
        setPhase(p => (p + 1) % 4)
      }, 400)
    }, duration - 400)
    timers.push(nextTimer)

    return () => {
      timers.forEach(t => { if (typeof t === 'number') clearTimeout(t); else clearInterval(t) })
    }
  }, [phase])

  const phaseLabels = ['RAG Pipeline', 'Live Query', 'Codebase Explorer', 'API Usage']

  return (
    <div className="auth-story">
      <div className={`phase-label ${visible ? 'visible' : ''}`}>
        <div className="phase-dot" />
        {phaseLabels[phase]}
      </div>

      <div className={`phase-content ${visible ? 'visible' : ''}`}>

        {/* PHASE 0 — RAG Pipeline */}
        {phase === 0 && (
          <div className="pipeline-diagram">
            <div className="pipeline-row">
              <div className={`pipeline-node ${pipelineStep >= 1 ? 'lit' : ''}`}>
                <span className="node-icon">💬</span> Your Question
              </div>
              <div className={`pipeline-arrow ${pipelineStep >= 2 ? 'lit' : ''}`}>→</div>
              <div className={`pipeline-node ${pipelineStep >= 2 ? 'lit' : ''}`}>
                <span className="node-icon">⚡</span> AST Parser
              </div>
            </div>
            <div className="pipeline-row" style={{ paddingLeft: '1rem' }}>
              <div className={`pipeline-arrow ${pipelineStep >= 3 ? 'lit' : ''}`} style={{ transform: 'rotate(90deg)' }}>→</div>
            </div>
            <div className="pipeline-row">
              <div className={`pipeline-node ${pipelineStep >= 3 ? 'lit' : ''}`}>
                <span className="node-icon">🔍</span> BM25 Search
              </div>
              <div className={`pipeline-merge-label ${pipelineStep >= 4 ? 'lit' : ''}`} style={{ margin: '0 0.5rem' }}>RRF k=60</div>
              <div className={`pipeline-node ${pipelineStep >= 3 ? 'lit' : ''}`}>
                <span className="node-icon">🧠</span> Semantic Search
              </div>
            </div>
            <div className="pipeline-row" style={{ paddingLeft: '1rem' }}>
              <div className={`pipeline-arrow ${pipelineStep >= 4 ? 'lit' : ''}`} style={{ transform: 'rotate(90deg)' }}>→</div>
            </div>
            <div className="pipeline-row">
              <div className={`pipeline-node ${pipelineStep >= 5 ? 'lit' : ''}`}>
                <span className="node-icon">🎯</span> Cohere Reranking
              </div>
              <div className={`pipeline-arrow ${pipelineStep >= 6 ? 'lit' : ''}`}>→</div>
              <div className={`pipeline-node ${pipelineStep >= 6 ? 'lit' : ''}`}>
                <span className="node-icon">✅</span> Cited Answer
              </div>
            </div>
          </div>
        )}

        {/* PHASE 1 — Live Query */}
        {phase === 1 && (
          <div className="query-simulation">
            <div className="sim-bar">
              <div className="sim-dot sim-dot-red" />
              <div className="sim-dot sim-dot-amber" />
              <div className="sim-dot sim-dot-green" />
            </div>
            <div className="sim-question">
              <div className="sim-avatar-user">S</div>
              <div className="sim-bubble-user">
                {simQuestion}
                {simQuestion.length < QUESTION_TEXT.length && <span className="sim-cursor" />}
              </div>
            </div>
            <div className={`sim-answer-wrap ${simAnswerVisible ? 'visible' : ''}`}>
              <div className="sim-avatar-ai">AI</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', flex: 1 }}>
                <div className="sim-bubble-ai">
                  {simAnswer}
                  {simAnswerVisible && simAnswer.length < ANSWER_TEXT.length && <span className="sim-cursor" />}
                </div>
                <div className={`sim-source-pill ${simSourceVisible ? 'visible' : ''}`}>
                  📌 auth/auth_service.py · L12–58 · score 0.94
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PHASE 2 — Codebase Explorer */}
        {phase === 2 && (
          <div className="explorer-wrap">
            <div className="explorer-titlebar">
              <div className="code-dot code-dot-red" />
              <div className="code-dot code-dot-amber" />
              <div className="code-dot code-dot-green" />
              <span className="explorer-title-text">your-project · indexing</span>
            </div>
            <div className="explorer-body">
              {EXPLORER_ITEMS.map(item => (
                <div
                  key={item.id}
                  className={[
                    'explorer-row',
                    item.indent ? `explorer-${item.indent}` : '',
                    explorerRows.includes(item.id) ? 'visible' : '',
                    explorerHighlight === item.id ? 'highlighted' : '',
                    explorerSearch === item.id ? 'searching' : '',
                  ].filter(Boolean).join(' ')}
                >
                  <span className="explorer-icon">{item.icon}</span>
                  <span className="explorer-name">{item.name}</span>
                  {item.badge && (
                    <span className={`explorer-badge ${explorerBadge === item.id ? 'visible' : ''}`}>
                      {item.badge}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* PHASE 3 — Code Block */}
        {phase === 3 && (
          <div className="auth-code-block">
            <div className="code-bar">
              <div className="code-dot code-dot-red" />
              <div className="code-dot code-dot-amber" />
              <div className="code-dot code-dot-green" />
            </div>
            <div className="code-line"><span className="code-ln">1</span><span className="c-purple">from</span><span className="c-white"> rag </span><span className="c-purple">import</span><span className="c-blue"> CodebaseAssistant</span></div>
            <div className="code-line"><span className="code-ln">2</span><span className="c-muted">&nbsp;</span></div>
            <div className="code-line"><span className="code-ln">3</span><span className="c-blue">assistant</span><span className="c-white"> = </span><span className="c-green">CodebaseAssistant</span><span className="c-white">(</span></div>
            <div className="code-line"><span className="code-ln">4</span><span className="c-white">&nbsp;&nbsp;repo</span><span className="c-white">=</span><span className="c-amber">"your-project"</span><span className="c-white">,</span></div>
            <div className="code-line"><span className="code-ln">5</span><span className="c-white">&nbsp;&nbsp;search</span><span className="c-white">=</span><span className="c-amber">"hybrid"</span><span className="c-white">,</span></div>
            <div className="code-line"><span className="code-ln">6</span><span className="c-white">)</span></div>
            <div className="code-line"><span className="code-ln">7</span><span className="c-muted">&nbsp;</span></div>
            <div className="code-line"><span className="code-ln">8</span><span className="c-blue">result</span><span className="c-white"> = assistant.</span><span className="c-green">ask</span><span className="c-white">(</span></div>
            <div className="code-line"><span className="code-ln">9</span><span className="c-white">&nbsp;&nbsp;</span><span className="c-amber">"How does auth work?"</span></div>
            <div className="code-line"><span className="code-ln">10</span><span className="c-white">)</span></div>
            <div className="code-line"><span className="code-ln">11</span><span className="c-muted">&nbsp;</span></div>
            <div className="code-line"><span className="code-ln">12</span><span className="c-purple">print</span><span className="c-white">(result.</span><span className="c-pink">answer</span><span className="c-white">, result.</span><span className="c-pink">sources</span><span className="c-white">)</span><span className="code-cursor" /></div>
          </div>
        )}

      </div>

      {/* Progress bars */}
      <div className="phase-progress-track">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="phase-progress-bar" onClick={() => { setVisible(false); setTimeout(() => setPhase(i), 400) }}>
            <div
              className={`phase-progress-fill ${i < phase ? 'done' : i === phase ? 'active' : ''}`}
              style={i === phase ? { width: `${progress}%`, transition: `width ${50}ms linear` } : {}}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

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

  // Intercept 401 responses — attempt silent token refresh before logging out.
  // Auth endpoints are excluded: their 401s mean wrong credentials, not expiry.
  useEffect(() => {
    const AUTH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']
    let isRefreshing = false
    let queue = []

    const processQueue = (error, newToken = null) => {
      queue.forEach(({ resolve, reject }) => error ? reject(error) : resolve(newToken))
      queue = []
    }

    const forceLogout = () => {
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

    const id = axios.interceptors.response.use(
      (res) => res,
      async (err) => {
        const original = err.config
        const url = original?.url || ''
        const isAuthEndpoint = AUTH_PATHS.some(p => url.includes(p))

        if (err.response?.status !== 401 || isAuthEndpoint || original._retry) {
          return Promise.reject(err)
        }

        if (isRefreshing) {
          return new Promise((resolve, reject) => queue.push({ resolve, reject }))
            .then(newToken => {
              original.headers.Authorization = `Bearer ${newToken}`
              return axios(original)
            })
        }

        original._retry = true
        isRefreshing = true

        try {
          const res = await axios.post(`${API_URL}/auth/refresh`)
          const newToken = res.data.access_token
          setToken(newToken)
          localStorage.setItem('token', newToken)
          original.headers.Authorization = `Bearer ${newToken}`
          processQueue(null, newToken)
          return axios(original)
        } catch {
          processQueue(new Error('Refresh failed'), null)
          forceLogout()
          return Promise.reject(err)
        } finally {
          isRefreshing = false
        }
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

  const logout = async () => {
    try { await axios.post(`${API_URL}/auth/logout`) } catch {}
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
          {/* ── LEFT PANEL ── */}
          <div className="auth-left">
            <div className="auth-left-bg" />

            <div className="auth-left-top">
              <div className="auth-left-logo">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent)' }}>
                  <polyline points="16 18 22 12 16 6"/>
                  <polyline points="8 6 2 12 8 18"/>
                </svg>
              </div>
              <span className="auth-left-brand">AI Codebase Assistant</span>
            </div>

            <div className="auth-left-middle">
              <div>
                <h2 className="auth-left-heading">
                  Ask anything about<br />
                  <span>any codebase.</span>
                </h2>
                <p className="auth-left-desc">
                  Upload a repository, ask questions in plain English,
                  and get cited answers with exact file and line references.
                </p>
              </div>

              <AuthStoryPanel />
            </div>

            <div className="auth-left-bottom">
              Built with FastAPI · RAG · MongoDB Atlas · OpenAI
            </div>
          </div>

          {/* ── RIGHT PANEL ── */}
          <div className="auth-right">
            <div className="auth-right-inner">
              <div className="auth-right-header">
                <h1 className="auth-right-title">
                  {isRegistering ? 'Create account' : 'Welcome back'}
                </h1>
                <p className="auth-right-sub">
                  {isRegistering
                    ? 'Start exploring your codebase in seconds.'
                    : 'Sign in to continue to your assistant.'}
                </p>
              </div>

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
          <div className="header-logo">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6"/>
              <polyline points="8 6 2 12 8 18"/>
            </svg>
          </div>
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
            <div className="section-label">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              Upload Repository
            </div>
            <div className="input-group">
              <label className={`upload-zone ${uploadFile ? 'has-file' : ''}`}>
                <svg className="upload-zone-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <span className="upload-zone-text">
                  {uploadFile ? uploadFile.name : 'Drop ZIP here or click to browse'}
                </span>
                {!uploadFile && <span className="upload-zone-sub">Supports .zip files</span>}
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
            <div className="section-label">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
              Import from GitHub
            </div>
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
            <div className="section-label">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              Active Repository
            </div>
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
            {activeRepo && (
              <div className="repo-card">
                <span className="repo-card-name">{activeRepo.name}</span>
                <span className={`repo-card-badge ${activeRepo.status}`}>
                  {activeRepo.status === 'indexed'
                    ? '✓ Ready'
                    : activeRepo.status === 'indexing'
                    ? 'Indexing…'
                    : 'Failed'}
                </span>
              </div>
            )}
          </div>

          {/* Re-index (only when repo selected) */}
          {selectedRepo && (
            <div className="sidebar-section">
              <div className="section-label">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                Re-index Repository
              </div>
              <div className="input-group">
                <label className={`upload-zone ${reindexFile ? 'has-file' : ''}`}>
                  <svg className="upload-zone-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polyline points="23 4 23 10 17 10"/>
                    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                  </svg>
                  <span className="upload-zone-text">
                    {reindexFile ? reindexFile.name : 'Drop updated ZIP here'}
                  </span>
                  {!reindexFile && <span className="upload-zone-sub">Replaces current index</span>}
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
                <div className="section-label" style={{ margin: 0 }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                  Conversations
                </div>
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
                        <span className="session-preview">
                          {session.first_message
                            ? session.first_message.slice(0, 28) + (session.first_message.length > 28 ? '…' : '')
                            : `Chat · ${formatTime(session.created_at)}`}
                        </span>
                        <span className="session-meta">
                          {session.message_count} msgs · {formatTime(session.updated_at || session.created_at)}
                        </span>
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
              <div className="empty-state-icon">
                <span className="empty-state-icon-svg">&lt;/&gt;</span>
              </div>
              <h3>AI Codebase Assistant</h3>
              <p>Upload or import a repository, then interrogate it in plain English.</p>
              <div className="empty-state-features">
                <div className="feature-row">
                  <span className="feature-row-icon">⟳</span>
                  Hybrid BM25 + semantic search with RRF fusion
                </div>
                <div className="feature-row">
                  <span className="feature-row-icon">◎</span>
                  Cohere reranking across 6 languages
                </div>
                <div className="feature-row">
                  <span className="feature-row-icon">▸</span>
                  Cited answers — exact file path + line numbers
                </div>
                <div className="feature-row">
                  <span className="feature-row-icon">≋</span>
                  Streaming SSE · persistent sessions · JWT auth
                </div>
              </div>
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
               <div className="messages-inner">
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
                              <span
                                className="score"
                                style={{
                                  color: src.score < 0 ? 'var(--amber)' : 'var(--green)',
                                  background: src.score < 0 ? 'rgba(245,158,11,0.1)' : 'var(--green-subtle)'
                                }}
                              >
                                {src.score?.toFixed(3)}
                              </span>
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
              </div>

              <div className="chat-input-area">
               <div className="chat-input-inner">
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
                    title="Send"
                  >
                    {chatLoading ? (
                      <div className="thinking-dots" style={{ gap: '3px' }}>
                        <span /><span /><span />
                      </div>
                    ) : (
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="12" y1="19" x2="12" y2="5"/>
                        <polyline points="5 12 12 5 19 12"/>
                      </svg>
                    )}
                  </button>
                </div>
                <p className="input-hint">Enter to send · Shift+Enter for new line</p>
               </div>
              </div>
            </>
          )}
        </section>

      </main>
    </div>
  )
}

export default App
