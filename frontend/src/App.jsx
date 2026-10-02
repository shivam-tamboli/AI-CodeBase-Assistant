import { useState, useEffect } from 'react'
import * as api from './api'
import Auth from './Auth'
import Sidebar from './Sidebar'
import Chat from './Chat'
import './App.css'

function App() {
  const [token, setToken] = useState(api.getToken())
  const [username, setUsername] = useState(api.getStoredUsername())

  // Repository state
  const [repositories, setRepositories] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')

  // Session state — shared by Sidebar (list) and Chat (messages)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [chatHistory, setChatHistory] = useState([])

  // Toast notifications
  const [toasts, setToasts] = useState([])
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // ── Toasts ────────────────────────────────────────────────────────────────

  const showToast = (message, type = 'info') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500)
  }

  const dismissToast = (id) => setToasts(prev => prev.filter(t => t.id !== id))

  // ── Data loading ──────────────────────────────────────────────────────────
  // Declared before the effects below that call them.

  const fetchRepositories = async () => {
    try {
      setRepositories(await api.listRepositories())
    } catch (err) {
      console.error('Failed to fetch repositories:', err)
    }
  }

  const fetchSessions = async (repoId) => {
    try {
      setSessions(await api.listSessions(repoId))
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
    }
  }

  // ── Auth lifecycle ────────────────────────────────────────────────────────

  const resetWorkspace = () => {
    setToken('')
    setUsername('')
    setRepositories([])
    setSessions([])
    setActiveSessionId(null)
    setChatHistory([])
    setSelectedRepo('')
  }

  // Silent token refresh on 401; if the refresh cookie is gone too, sign out.
  useEffect(() => api.installAuthRefresh({
    onRefreshed: setToken,
    onExpired: () => {
      resetWorkspace()
      showToast('Session expired — please sign in again', 'error')
    },
  }), [])

  // Load repos on mount if already logged in (fixes page-refresh bug)
  useEffect(() => {
    if (token) fetchRepositories()
  }, [])

  // On the login page, poke the backend right away so a Render cold start
  // (~50s) overlaps with the user reading and typing, not with the spinner.
  useEffect(() => {
    if (!token) api.pingHealth()
  }, [token])

  const handleAuthenticated = (newToken, name) => {
    setToken(newToken)
    setUsername(name)
    fetchRepositories()
  }

  const logout = async () => {
    try { await api.logout() } catch {}
    api.clearSession()
    resetWorkspace()
  }

  // ── Sessions ──────────────────────────────────────────────────────────────

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

  const startNewSession = async () => {
    if (!selectedRepo) return
    try {
      setActiveSessionId(await api.createSession(selectedRepo))
      setChatHistory([])
      fetchSessions(selectedRepo)
    } catch (err) {
      showToast('Failed to create session: ' + api.apiError(err), 'error')
    }
  }

  const selectSession = async (sessionId) => {
    setActiveSessionId(sessionId)
    try {
      setChatHistory(await api.getSessionHistory(sessionId, 50))
    } catch (err) {
      console.error('Failed to load session history:', err)
      setChatHistory([])
    }
  }

  const deleteSession = async (sessionId, e) => {
    e.stopPropagation()
    try {
      await api.deleteSession(sessionId)
      if (activeSessionId === sessionId) {
        setActiveSessionId(null)
        setChatHistory([])
      }
      fetchSessions(selectedRepo)
    } catch {
      showToast('Failed to delete session', 'error')
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const toastContainer = (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`} onClick={() => dismissToast(t.id)}>
          {t.message}
        </div>
      ))}
    </div>
  )

  if (!token) {
    return (
      <>
        <Auth onAuthenticated={handleAuthenticated} showToast={showToast} />
        {toastContainer}
      </>
    )
  }

  const activeRepo = repositories.find(r => r.id === selectedRepo)

  return (
    <div className="app">
      {toastContainer}

      <header>
        <div className="header-brand">
          <button
            className="mobile-menu-btn"
            onClick={() => setSidebarOpen(prev => !prev)}
            title="Toggle menu"
            aria-label="Toggle sidebar menu"
          >
            {sidebarOpen ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            )}
          </button>
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
        <Sidebar
          sidebarOpen={sidebarOpen}
          repositories={repositories}
          selectedRepo={selectedRepo}
          activeRepo={activeRepo}
          onSelectRepo={setSelectedRepo}
          refreshRepositories={fetchRepositories}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewSession={startNewSession}
          onSelectSession={selectSession}
          onDeleteSession={deleteSession}
        />
        <Chat
          username={username}
          selectedRepo={selectedRepo}
          activeRepo={activeRepo}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
          activeSessionId={activeSessionId}
          setActiveSessionId={setActiveSessionId}
          refreshSessions={() => fetchSessions(selectedRepo)}
          showToast={showToast}
        />
      </main>
    </div>
  )
}

export default App
