import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import * as api from './api'
import { formatTime } from './format'

const HINTS = [
  'How does authentication work?',
  'Where is the main entry point?',
  'Explain the database schema',
  'How are errors handled?',
]

// Chat area: empty states, message list with sources, and the input box.
// Owns the draft question and streaming state; the conversation itself
// (history + active session) is shared with Sidebar, so it lives in App.
export default function Chat({
  username,
  selectedRepo,
  activeRepo,
  chatHistory,
  setChatHistory,
  activeSessionId,
  setActiveSessionId,
  refreshSessions,
  showToast,
  onTryDemo,
  demoLoading,
}) {
  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // Auto-scroll ref
  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  const repoStatus = activeRepo?.status
  const repoReady = repoStatus === 'indexed'
  const isDemo = Boolean(activeRepo?.is_demo)
  // The demo comes with questions written for that repo; others get generic ones.
  const hints = isDemo && activeRepo.suggested_questions?.length ? activeRepo.suggested_questions : HINTS

  const askQuestion = async () => {
    if (!question.trim() || !selectedRepo) return

    let sessionId = activeSessionId
    if (!sessionId) {
      try {
        sessionId = await api.createSession(selectedRepo)
        setActiveSessionId(sessionId)
        refreshSessions()
      } catch (err) {
        showToast('Could not create session: ' + api.apiError(err), 'error')
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
      const response = await api.streamQuery({
        question: userMessage, repository_id: selectedRepo, session_id: sessionId, limit: 5
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
            if (event.type === 'done') refreshSessions()
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

  return (
    <section className="chat-section">
      {!selectedRepo ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <span className="empty-state-icon-svg">&lt;/&gt;</span>
          </div>
          <h3>AI Codebase Assistant</h3>
          <p>Upload or import a repository, then interrogate it in plain English.</p>
          <button className="btn btn-primary demo-cta" onClick={onTryDemo} disabled={demoLoading}>
            {demoLoading ? 'Loading demo…' : 'Try a demo repo'}
          </button>
          <span className="demo-cta-sub">No setup — a small open-source repo that's already indexed</span>
          <div className="empty-state-features">
            <div className="feature-row">
              <span className="feature-row-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </span>
              Hybrid BM25 + semantic search with RRF fusion
            </div>
            <div className="feature-row">
              <span className="feature-row-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6"/>
                  <line x1="3" y1="12" x2="15" y2="12"/>
                  <line x1="3" y1="18" x2="9" y2="18"/>
                  <polyline points="17 15 21 12 17 9"/>
                </svg>
              </span>
              Cohere reranking of hybrid search results
            </div>
            <div className="feature-row">
              <span className="feature-row-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                  <polyline points="10 9 9 9 8 9"/>
                </svg>
              </span>
              Cited answers — exact file path + line numbers
            </div>
            <div className="feature-row">
              <span className="feature-row-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </span>
              Streaming SSE · persistent sessions · JWT auth
            </div>
          </div>
        </div>
      ) : (
        <>
          {isDemo && (
            <div className="demo-banner">
              <span className="demo-banner-tag">Demo</span>
              Demo repo — ask anything about this codebase
              {activeRepo.source_url && (
                <a href={activeRepo.source_url} target="_blank" rel="noreferrer">
                  {activeRepo.source_url.replace('https://github.com/', '')}
                </a>
              )}
            </div>
          )}

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
                    {hints.map(hint => (
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
                      <span className="sources-order">· ranked by relevance</span>
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
                          {/* Raw scores aren't comparable between Cohere and the
                              fallback ranker, but the order is: sources arrive best-first. */}
                          <span
                            className={`source-rank${j === 0 ? ' top' : ''}`}
                            title="Sources are listed from most to least relevant"
                          >
                            {j === 0 ? 'Best match' : `#${j + 1}`}
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
                placeholder={repoReady ? 'e.g. How does the auth middleware work?' : 'Indexing in progress — almost ready…'}
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
  )
}
