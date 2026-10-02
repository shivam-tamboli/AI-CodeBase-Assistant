import React, { useState } from 'react'
import * as api from './api'

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
  const PHASES = ['RAG Pipeline', 'Live Query', 'Codebase Explorer', 'REST API']

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
      timers.push(setTimeout(() => setPipelineStep(1), 300))
      timers.push(setTimeout(() => setPipelineStep(2), 900))
      timers.push(setTimeout(() => setPipelineStep(3), 1500))
      timers.push(setTimeout(() => setPipelineStep(4), 2100))
      timers.push(setTimeout(() => setPipelineStep(5), 2900))
      timers.push(setTimeout(() => setPipelineStep(6), 3700))
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

  const phaseLabels = ['RAG Pipeline', 'Live Query', 'Codebase Explorer', 'REST API']

  return (
    <div className="auth-story">
      <div className={`phase-label ${visible ? 'visible' : ''}`}>
        <div className="phase-dot" />
        {phaseLabels[phase]}
        <span className="phase-counter">0{phase + 1} / 04</span>
      </div>

      <div className={`phase-content ${visible ? 'visible' : ''}`}>

        {/* PHASE 0 — RAG Pipeline */}
        {phase === 0 && (
          <div className="pipeline-wrap">

            {/* Row 1: Question → AST Parser → Split */}
            <div className="pipeline-track">
              <div className={`pipeline-node-v2 ${pipelineStep >= 1 ? 'lit' : ''}`}>
                <div className="pipeline-node-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <span className="pipeline-node-label">Query</span>
              </div>
              <div className="pipeline-connector">
                <div className={`pipeline-connector-fill cyan ${pipelineStep >= 2 ? 'active' : ''}`} />
              </div>
              <div className={`pipeline-node-v2 ${pipelineStep >= 2 ? 'lit' : ''}`}>
                <div className="pipeline-node-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="16 18 22 12 16 6"/>
                    <polyline points="8 6 2 12 8 18"/>
                  </svg>
                </div>
                <span className="pipeline-node-label">AST Parse</span>
              </div>
              <div className="pipeline-connector">
                <div className={`pipeline-connector-fill cyan ${pipelineStep >= 3 ? 'active' : ''}`} />
              </div>
              <div className={`pipeline-node-v2 ${pipelineStep >= 3 ? 'lit' : ''}`}>
                <div className="pipeline-node-box">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="3" width="6" height="18" rx="1"/>
                    <rect x="9" y="3" width="6" height="18" rx="1"/>
                    <rect x="16" y="3" width="6" height="18" rx="1"/>
                  </svg>
                </div>
                <span className="pipeline-node-label">Chunk</span>
              </div>
            </div>

            {/* Row 2: Dual search streams merging */}
            <div className="pipeline-merge">
              <div className="pipeline-merge-row">
                <div className={`pipeline-merge-branch ${pipelineStep >= 4 ? 'lit' : ''}`}>
                  <div className="pipeline-branch-node cyan">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="4" y1="6" x2="20" y2="6"/>
                      <line x1="4" y1="12" x2="14" y2="12"/>
                      <line x1="4" y1="18" x2="10" y2="18"/>
                    </svg>
                    BM25
                  </div>
                  <div className="pipeline-branch-line">
                    <div className={`pipeline-branch-line-fill cyan ${pipelineStep >= 5 ? 'active' : ''}`} />
                  </div>
                </div>
                <div className={`pipeline-rrf-badge ${pipelineStep >= 5 ? 'lit' : ''}`}>RRF k=60</div>
              </div>
              <div className="pipeline-merge-row">
                <div className={`pipeline-merge-branch ${pipelineStep >= 4 ? 'lit' : ''}`}>
                  <div className="pipeline-branch-node purple">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 12 Q6 6 10 12 Q14 18 18 12 Q20 9 22 12"/>
                    </svg>
                    Semantic
                  </div>
                  <div className="pipeline-branch-line">
                    <div className={`pipeline-branch-line-fill purple ${pipelineStep >= 5 ? 'active' : ''}`} />
                  </div>
                </div>
              </div>
            </div>

            {/* Row 3: Reranker → Answer */}
            <div className="pipeline-track" style={{ justifyContent: 'center', gap: '0' }}>
              <div
                style={{
                  opacity: pipelineStep >= 5 ? 1 : 0,
                  transform: pipelineStep >= 5 ? 'translateY(0)' : 'translateY(8px)',
                  transition: 'all 0.4s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.35rem'
                }}
              >
                <div className={`pipeline-node-box ${pipelineStep >= 5 ? 'lit-purple-box' : ''}`}
                     style={{
                       borderColor: pipelineStep >= 5 ? 'rgba(191,95,255,0.6)' : 'rgba(0,245,255,0.15)',
                       boxShadow: pipelineStep >= 5 ? '0 0 16px rgba(191,95,255,0.25), inset 0 0 8px rgba(191,95,255,0.05)' : 'none',
                       background: pipelineStep >= 5 ? 'rgba(191,95,255,0.05)' : 'var(--bg-elevated)',
                       color: pipelineStep >= 5 ? 'var(--purple)' : 'var(--text-muted)',
                     }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="3" y1="6" x2="21" y2="6"/>
                    <line x1="3" y1="12" x2="15" y2="12"/>
                    <line x1="3" y1="18" x2="9" y2="18"/>
                    <polyline points="17 15 21 12 17 9"/>
                  </svg>
                </div>
                <span className="pipeline-node-label" style={{ color: pipelineStep >= 5 ? 'var(--purple)' : 'var(--text-muted)' }}>
                  Cohere Rerank
                </span>
              </div>

              <div className="pipeline-connector" style={{ minWidth: '60px', maxWidth: '120px' }}>
                <div className={`pipeline-connector-fill purple ${pipelineStep >= 6 ? 'active' : ''}`} />
              </div>

              <div
                style={{
                  opacity: pipelineStep >= 6 ? 1 : 0,
                  transform: pipelineStep >= 6 ? 'translateY(0)' : 'translateY(8px)',
                  transition: 'all 0.4s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.35rem'
                }}
              >
                <div className="pipeline-node-box"
                     style={{
                       borderColor: pipelineStep >= 6 ? 'rgba(0,255,159,0.6)' : 'rgba(0,245,255,0.15)',
                       boxShadow: pipelineStep >= 6 ? '0 0 16px rgba(0,255,159,0.25), inset 0 0 8px rgba(0,255,159,0.05)' : 'none',
                       background: pipelineStep >= 6 ? 'rgba(0,255,159,0.05)' : 'var(--bg-elevated)',
                       color: pipelineStep >= 6 ? 'var(--green)' : 'var(--text-muted)',
                     }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="8 12 11 15 16 9"/>
                  </svg>
                </div>
                <span className="pipeline-node-label" style={{ color: pipelineStep >= 6 ? 'var(--green)' : 'var(--text-muted)' }}>
                  Cited Answer
                </span>
              </div>

              <div className="pipeline-connector" style={{ minWidth: '40px', maxWidth: '80px' }}>
                <div className={`pipeline-connector-fill green ${pipelineStep >= 6 ? 'active' : ''}`} />
              </div>

              <div
                style={{
                  alignSelf: 'center',
                  marginBottom: '1.4rem',
                  opacity: pipelineStep >= 6 ? 1 : 0,
                  transition: 'opacity 0.3s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.1rem',
                }}
              >
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '0.65rem',
                  color: 'var(--green)',
                  textShadow: '0 0 8px rgba(0,255,159,0.5)',
                  whiteSpace: 'nowrap',
                }}>
                  score: 0.94
                </span>
                <span className="pipeline-score-label">relevance</span>
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
              <span className="explorer-title-text">
                <span className="explorer-indexing-dot" />
                your-project · indexing
              </span>
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
            <div className="code-line"><span className="code-ln">1</span><span className="code-text"><span className="c-muted">{'# Import a public repo — indexing runs in the background'}</span></span></div>
            <div className="code-line"><span className="code-ln">2</span><span className="code-text"><span className="c-purple">{'POST'}</span><span className="c-white">{' /repositories/import'}</span></span></div>
            <div className="code-line"><span className="code-ln">3</span><span className="code-text"><span className="c-blue">{'Authorization: '}</span><span className="c-amber">{'Bearer <token>'}</span></span></div>
            <div className="code-line"><span className="code-ln">4</span><span className="code-text"><span className="c-white">{'{"url": '}</span><span className="c-amber">{'"https://github.com/pallets/itsdangerous"'}</span><span className="c-white">{'}'}</span></span></div>
            <div className="code-line"><span className="code-ln">5</span><span className="code-text"><span className="c-muted">{' '}</span></span></div>
            <div className="code-line"><span className="code-ln">6</span><span className="code-text"><span className="c-muted">{'# Ask a question — the answer streams back as SSE'}</span></span></div>
            <div className="code-line"><span className="code-ln">7</span><span className="code-text"><span className="c-purple">{'POST'}</span><span className="c-white">{' /chat/query/stream'}</span></span></div>
            <div className="code-line"><span className="code-ln">8</span><span className="code-text"><span className="c-white">{'{"repository_id": '}</span><span className="c-amber">{'"<id>"'}</span><span className="c-white">{', "question": '}</span><span className="c-amber">{'"How are tokens signed?"'}</span><span className="c-white">{'}'}</span></span></div>
            <div className="code-line"><span className="code-ln">9</span><span className="code-text"><span className="c-muted">{' '}</span></span></div>
            <div className="code-line"><span className="code-ln">10</span><span className="code-text"><span className="c-green">{'data: '}</span><span className="c-white">{'{"type": "token", "answer": '}</span><span className="c-amber">{'"Tokens are signed by…"'}</span><span className="c-white">{'}'}</span></span></div>
            <div className="code-line"><span className="code-ln">11</span><span className="code-text"><span className="c-green">{'data: '}</span><span className="c-white">{'{"type": "done", "sources": [{"file_path": '}</span><span className="c-amber">{'"src/itsdangerous/signer.py"'}</span><span className="c-white">{', …}]}'}</span></span><span className="code-cursor" /></div>
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

function AuthLoadingButton({ isLoading, isRegistering, disabled, onClick }) {
  const [msgIndex, setMsgIndex] = React.useState(0)
  const [showNote, setShowNote] = React.useState(false)

  const loginMessages = [
    'Signing in...',
    'Connecting to server...',
    'Server is waking up...',
    'Almost there, hang tight...',
  ]

  const registerMessages = [
    'Creating account...',
    'Connecting to server...',
    'Server is waking up...',
    'Almost there, hang tight...',
  ]

  const messages = isRegistering ? registerMessages : loginMessages

  React.useEffect(() => {
    if (!isLoading) {
      setMsgIndex(0)
      setShowNote(false)
      return
    }

    setShowNote(false)

    const timers = []

    timers.push(setTimeout(() => setMsgIndex(1), 5000))
    timers.push(setTimeout(() => {
      setMsgIndex(2)
      setShowNote(true)
    }, 15000))
    timers.push(setTimeout(() => setMsgIndex(3), 30000))

    return () => timers.forEach(t => clearTimeout(t))
  }, [isLoading])

  return (
    <div style={{ width: '100%' }}>
      <button
        className={`auth-submit ${isLoading ? 'is-loading' : ''}`}
        onClick={onClick}
        disabled={disabled || isLoading}
        style={{ width: '100%' }}
      >
        {isLoading ? (
          <span className="auth-spinner">
            <span className="auth-spinner-ring" />
            <span className="auth-spinner-text">{messages[msgIndex]}</span>
          </span>
        ) : (
          isRegistering ? 'Create account' : 'Sign in'
        )}
      </button>

      <div className={`cold-start-note ${showNote ? 'visible' : ''}`}>
        <span className="cold-start-note-icon">ⓘ</span>
        <span className="cold-start-note-text">
          <strong>Server cold start</strong> — free tier wakes up in ~60s.
          Hang tight, it's working.
        </span>
      </div>
    </div>
  )
}

export default function Auth({ onAuthenticated, showToast }) {
  const [isRegistering, setIsRegistering] = useState(false)
  const [authUsername, setAuthUsername] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  const submit = async () => {
    setAuthLoading(true)
    try {
      const token = isRegistering
        ? await api.register(authUsername, authPassword)
        : await api.login(authUsername, authPassword)
      api.saveSession(token, authUsername)
      onAuthenticated(token, authUsername)
    } catch (err) {
      showToast((isRegistering ? 'Registration failed: ' : 'Login failed: ') + api.apiError(err), 'error')
    } finally {
      setAuthLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      {/* ── LEFT PANEL ── */}
      <div className="auth-left">
        <div className="auth-left-bg" />

        <div className="auth-left-top">
          <div className="auth-left-logo">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#00f5ff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6"/>
              <polyline points="8 6 2 12 8 18"/>
            </svg>
          </div>
          <span className="auth-left-brand">AI Codebase Assistant</span>
        </div>

        <div className="auth-left-middle">
          <div>
            <h2 className="auth-left-heading">
              Ask anything about
              <span>any codebase.</span>
            </h2>
            <p className="auth-left-desc">
              Upload a repository, ask questions in plain English,
              and get cited answers with exact file and line references.
            </p>
          </div>

          <AuthStoryPanel />

          <div className="auth-left-stats">
            <div className="auth-stat">
              <span className="auth-stat-value">6</span>
              <span className="auth-stat-label">AST-parsed languages</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat-value">15</span>
              <span className="auth-stat-label">File types indexed</span>
            </div>
            <div className="auth-stat">
              <span className="auth-stat-value">SSE</span>
              <span className="auth-stat-label">Streaming</span>
            </div>
          </div>
        </div>

        <div className="auth-left-bottom">
          <span>FastAPI</span>
          <span className="auth-footer-sep">|</span>
          <span>RAG Pipeline</span>
          <span className="auth-footer-sep">|</span>
          <span>MongoDB Atlas</span>
          <span className="auth-footer-sep">|</span>
          <span>OpenAI</span>
          <span className="auth-footer-sep">|</span>
          <span>Cohere</span>
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
                onKeyDown={(e) => e.key === 'Enter' && submit()}
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
                onKeyDown={(e) => e.key === 'Enter' && submit()}
                autoComplete={isRegistering ? 'new-password' : 'current-password'}
              />
            </div>
            <AuthLoadingButton
              isLoading={authLoading}
              isRegistering={isRegistering}
              disabled={!authUsername || !authPassword}
              onClick={submit}
            />
            <div className="auth-toggle">
              {isRegistering ? 'Already have an account?' : "Don't have an account?"}
              <button onClick={() => setIsRegistering(!isRegistering)}>
                {isRegistering ? 'Sign in' : 'Register'}
              </button>
            </div>
            <p style={{
              marginTop: '1.25rem',
              fontSize: '0.8rem',
              color: 'rgba(255,255,255,0.6)',
              textAlign: 'center',
              lineHeight: '1.5',
            }}>
              ⓘ First sign in may take up to 60s — server cold start
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
