import { useState, useEffect } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [isRegistering, setIsRegistering] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // Repository state
  const [repositories, setRepositories] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')

  // Session state
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [chatHistory, setChatHistory] = useState([])

  // Upload state
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadStatus, setUploadStatus] = useState('')

  // Reindex state
  const [reindexFile, setReindexFile] = useState(null)
  const [reindexStatus, setReindexStatus] = useState('')

  // GitHub import state
  const [githubUrl, setGithubUrl] = useState('')
  const [importStatus, setImportStatus] = useState('')

  // Chat state
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)

  // Load repos on mount if token already exists (fixes page refresh bug)
  useEffect(() => {
    if (token) fetchRepositories(token)
  }, [])

  // Load sessions whenever the selected repo changes
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

  // ── Auth ──────────────────────────────────────────────────────────────────

  const login = async () => {
    try {
      const res = await axios.post(`${API_URL}/auth/login`, { username, password })
      const newToken = res.data.access_token
      setToken(newToken)
      localStorage.setItem('token', newToken)
      fetchRepositories(newToken)
    } catch (err) {
      alert('Login failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  const register = async () => {
    try {
      const res = await axios.post(`${API_URL}/auth/register`, { username, password })
      const newToken = res.data.access_token
      setToken(newToken)
      localStorage.setItem('token', newToken)
      fetchRepositories(newToken)
    } catch (err) {
      alert('Registration failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  const logout = () => {
    setToken('')
    localStorage.removeItem('token')
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
    setLoading(true)
    setUploadStatus('Uploading and indexing...')

    const formData = new FormData()
    formData.append('file', uploadFile)

    try {
      await axios.post(`${API_URL}/repositories/upload`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      })
      setUploadStatus('Done! Repository indexed.')
      setUploadFile(null)
      fetchRepositories(token)
    } catch (err) {
      setUploadStatus('Upload failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setTimeout(() => setUploadStatus(''), 4000)
    }
  }

  const handleGitHubImport = async () => {
    if (!githubUrl.trim()) return
    setLoading(true)
    setImportStatus('Cloning and indexing...')
    try {
      await axios.post(`${API_URL}/repositories/import`,
        { url: githubUrl.trim() },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setImportStatus('Done! Repository indexed.')
      setGithubUrl('')
      fetchRepositories(token)
    } catch (err) {
      setImportStatus('Import failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setTimeout(() => setImportStatus(''), 5000)
    }
  }

  const handleReindex = async () => {
    if (!reindexFile || !selectedRepo) return
    setLoading(true)
    setReindexStatus('Re-indexing...')
    const formData = new FormData()
    formData.append('file', reindexFile)
    try {
      const res = await axios.post(`${API_URL}/repositories/${selectedRepo}/reindex`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      })
      const { files_changed, files_removed, chunks_created } = res.data
      setReindexStatus(`Done — ${files_changed} changed, ${files_removed} removed, ${chunks_created} new chunks`)
      setReindexFile(null)
    } catch (err) {
      setReindexStatus('Failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
      setTimeout(() => setReindexStatus(''), 5000)
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
      const res = await axios.post(`${API_URL}/chat/sessions`,
        { repository_id: selectedRepo },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      const newSessionId = res.data.session_id
      setActiveSessionId(newSessionId)
      setChatHistory([])
      fetchSessions(selectedRepo)
    } catch (err) {
      alert('Failed to create session: ' + (err.response?.data?.detail || err.message))
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
    if (!confirm('Delete this conversation?')) return
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
      alert('Failed to delete session: ' + (err.response?.data?.detail || err.message))
    }
  }

  // ── Chat ──────────────────────────────────────────────────────────────────

  const askQuestion = async () => {
    if (!question.trim() || !selectedRepo) return

    // Ensure we have an active session
    let sessionId = activeSessionId
    if (!sessionId) {
      try {
        const res = await axios.post(`${API_URL}/chat/sessions`,
          { repository_id: selectedRepo },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        sessionId = res.data.session_id
        setActiveSessionId(sessionId)
        fetchSessions(selectedRepo)
      } catch (err) {
        alert('Could not create session: ' + (err.response?.data?.detail || err.message))
        return
      }
    }

    const userMessage = question.trim()
    setQuestion('')
    setLoading(true)

    // Add user message and an empty assistant placeholder
    const assistantPlaceholder = { role: 'assistant', content: '', sources: [], timestamp: new Date().toISOString() }
    setChatHistory(prev => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
      assistantPlaceholder
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
        buffer = lines.pop()   // keep incomplete line for next iteration

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
          } catch { /* malformed line — skip */ }
        }
      }
    } catch (err) {
      setChatHistory(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { ...updated[updated.length - 1], content: 'Error: ' + err.message }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      askQuestion()
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  const formatTime = (isoString) => {
    if (!isoString) return ''
    const d = new Date(isoString)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  // ── Auth Screen ───────────────────────────────────────────────────────────

  if (!token) {
    return (
      <div className="app">
        <header>
          <h1>AI Codebase Assistant</h1>
          <p>Ask questions about your code</p>
        </header>
        <main>
          <div className="login-form">
            <h2>{isRegistering ? 'Create Account' : 'Login'}</h2>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (isRegistering ? register() : login())}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (isRegistering ? register() : login())}
            />
            <button onClick={isRegistering ? register : login} disabled={!username || !password}>
              {isRegistering ? 'Create Account' : 'Login'}
            </button>
            <p className="toggle-auth">
              {isRegistering ? 'Already have an account?' : "Don't have an account?"}
              <button className="link-btn" onClick={() => setIsRegistering(!isRegistering)}>
                {isRegistering ? ' Login' : ' Register'}
              </button>
            </p>
          </div>
        </main>
      </div>
    )
  }

  // ── Main App ──────────────────────────────────────────────────────────────

  return (
    <div className="app">
      <header>
        <h1>AI Codebase Assistant</h1>
        <div className="header-right">
          <span className="username-label">{username || 'Logged in'}</span>
          <button className="logout-btn" onClick={logout}>Logout</button>
        </div>
      </header>

      <main className="main-layout">

        {/* ── LEFT SIDEBAR ─────────────────────────────────────────────── */}
        <aside className="sidebar">
          <section className="upload-section">
            <h2>Upload Repository</h2>
            <div className="upload-form">
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setUploadFile(e.target.files[0])}
              />
              <button onClick={handleUpload} disabled={loading || !uploadFile}>
                {uploadStatus || 'Upload ZIP'}
              </button>
            </div>
          </section>

          <section className="upload-section">
            <h2>Import from GitHub</h2>
            <div className="upload-form">
              <input
                type="url"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGitHubImport()}
              />
              <button onClick={handleGitHubImport} disabled={loading || !githubUrl.trim()}>
                {importStatus || 'Import'}
              </button>
            </div>
          </section>

          <section className="repo-section">
            <h2>Repository</h2>
            <select
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
              className="repo-select-dropdown"
            >
              <option value="">-- Select a repository --</option>
              {repositories.map(repo => (
                <option key={repo.id} value={repo.id}>{repo.name}</option>
              ))}
            </select>
          </section>

          {selectedRepo && (
            <section className="upload-section">
              <h2>Re-index Repository</h2>
              <div className="upload-form">
                <input
                  type="file"
                  accept=".zip"
                  onChange={(e) => setReindexFile(e.target.files[0])}
                />
                <button onClick={handleReindex} disabled={loading || !reindexFile}>
                  {reindexStatus || 'Re-index ZIP'}
                </button>
              </div>
            </section>
          )}

          {selectedRepo && (
            <section className="sessions-section">
              <div className="sessions-header">
                <h2>Conversations</h2>
                <button className="new-chat-btn" onClick={startNewSession}>+ New Chat</button>
              </div>

              {sessions.length === 0 ? (
                <p className="no-sessions">No conversations yet. Click "+ New Chat" to start.</p>
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
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </aside>

        {/* ── CHAT AREA ─────────────────────────────────────────────────── */}
        <section className="chat-section">
          {!selectedRepo ? (
            <div className="empty-state">
              <p>Select a repository from the sidebar to start asking questions.</p>
              <p>If you don't have one yet, upload a ZIP file first.</p>
            </div>
          ) : (
            <>
              {activeSessionId && (
                <div className="session-badge">
                  Conversation active · {chatHistory.length} messages
                </div>
              )}

              <div className="chat-messages">
                {chatHistory.length === 0 && (
                  <div className="empty-chat">
                    <p>Ask a question about your codebase below.</p>
                    <p className="hint">Try: "How does authentication work?" or "Where is the main entry point?"</p>
                  </div>
                )}

                {chatHistory.map((msg, i) => (
                  <div key={i} className={`message message-${msg.role}`}>
                    <div className="message-role">{msg.role === 'user' ? 'You' : 'Assistant'}</div>
                    <div className="message-content">
                      {msg.role === 'assistant'
                        ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                        : msg.content}
                    </div>

                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources">
                        <div className="sources-title">Sources ({msg.sources.length} chunks)</div>
                        <ul>
                          {msg.sources.map((src, j) => (
                            <li key={j}>
                              <code>{src.file_path || '(unknown file)'}</code>
                              {src.start_line > 0 && (
                                <span> lines {src.start_line}–{src.end_line}</span>
                              )}
                              {src.name && <span className="chunk-name"> · {src.chunk_type}: {src.name}</span>}
                              <span className="score">{src.score?.toFixed(3)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className="message-time">{formatTime(msg.timestamp)}</div>
                  </div>
                ))}

                {loading && (
                  <div className="message message-assistant">
                    <div className="message-role">Assistant</div>
                    <div className="message-content thinking">Thinking...</div>
                  </div>
                )}
              </div>

              <div className="chat-input-area">
                <textarea
                  placeholder="Ask a question about your code... (Enter to send, Shift+Enter for new line)"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={3}
                  disabled={loading}
                />
                <button
                  onClick={askQuestion}
                  disabled={loading || !question.trim()}
                  className="send-btn"
                >
                  {loading ? 'Thinking...' : 'Ask'}
                </button>
              </div>
            </>
          )}
        </section>

      </main>
    </div>
  )
}

export default App
