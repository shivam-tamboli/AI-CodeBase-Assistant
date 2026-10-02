import { useState, useRef } from 'react'
import * as api from './api'
import { formatTime } from './format'

// Upload / import / re-index forms, repository picker and conversation list.
// Owns the form state for those panels; repositories, sessions and the
// selection are shared with Chat, so they live in App and come in as props.
export default function Sidebar({
  sidebarOpen,
  repositories,
  selectedRepo,
  activeRepo,
  onSelectRepo,
  refreshRepositories,
  sessions,
  activeSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
}) {
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
  const [githubToken, setGithubToken] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [importStatus, setImportStatus] = useState(null)

  // File input refs — needed to reset native input value so same file can be re-selected
  const uploadInputRef = useRef(null)
  const reindexInputRef = useRef(null)

  const pollRepoStatus = (repoId, setStatus) => {
    const interval = setInterval(async () => {
      try {
        const { status, name, error } = await api.getRepositoryStatus(repoId)
        if (status === 'indexed') {
          clearInterval(interval)
          setStatus({ type: 'success', text: `"${name}" indexed successfully` })
          refreshRepositories()
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

  const handleUpload = async () => {
    if (!uploadFile) return
    setUploadLoading(true)
    setUploadStatus({ type: 'loading', text: 'Uploading...' })
    try {
      const { id: repoId } = await api.uploadRepository(uploadFile)
      // Clear file state and native input so same file can be re-selected
      setUploadFile(null)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
      setUploadStatus({ type: 'loading', text: 'Indexing code...' })
      // Show repo in dropdown immediately (as pending) and auto-select it
      await refreshRepositories()
      onSelectRepo(repoId)
      // Continue polling until indexed/failed
      pollRepoStatus(repoId, setUploadStatus)
    } catch (err) {
      setUploadStatus({ type: 'error', text: 'Upload failed: ' + api.apiError(err) })
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
      const { id: repoId } = await api.importRepository(githubUrl.trim(), githubToken.trim())
      setGithubUrl('')
      setGithubToken('')
      setImportStatus({ type: 'loading', text: 'Indexing code...' })
      // Show repo in dropdown immediately and auto-select it
      await refreshRepositories()
      onSelectRepo(repoId)
      pollRepoStatus(repoId, setImportStatus)
    } catch (err) {
      setImportStatus({ type: 'error', text: 'Import failed: ' + api.apiError(err) })
      setTimeout(() => setImportStatus(null), 6000)
    } finally {
      setImportLoading(false)
    }
  }

  const handleReindex = async () => {
    if (!reindexFile || !selectedRepo) return
    setReindexLoading(true)
    setReindexStatus({ type: 'loading', text: 'Uploading...' })
    try {
      const res = await api.reindexRepository(selectedRepo, reindexFile)
      setReindexFile(null)
      if (reindexInputRef.current) reindexInputRef.current.value = ''
      setReindexStatus({ type: 'loading', text: 'Re-indexing...' })
      pollRepoStatus(res.repository_id || selectedRepo, setReindexStatus)
    } catch (err) {
      setReindexStatus({ type: 'error', text: 'Failed: ' + api.apiError(err) })
      setTimeout(() => setReindexStatus(null), 5000)
    } finally {
      setReindexLoading(false)
    }
  }

  return (
    <aside className={`sidebar ${sidebarOpen ? 'mobile-open' : ''}`}>

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
          <input
            className="text-input"
            type="password"
            placeholder="Access token (private repos only)"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGitHubImport()}
            autoComplete="off"
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
          onChange={(e) => onSelectRepo(e.target.value)}
        >
          <option value="">-- Select a repository --</option>
          {repositories.map(repo => (
            <option key={repo.id} value={repo.id}>
              {repo.name}{repo.is_demo ? ' (demo)' : ''}{repo.status && repo.status !== 'indexed' ? ` (${repo.status}…)` : ''}
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

      {/* Re-index (only for the user's own repos — the demo is read-only) */}
      {selectedRepo && !activeRepo?.is_demo && (
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
            <button className="btn btn-new-chat" onClick={onNewSession}>+ New</button>
          </div>
          {sessions.length === 0 ? (
            <p className="no-sessions">No conversations yet</p>
          ) : (
            <ul className="sessions-list">
              {sessions.map(session => (
                <li
                  key={session.id}
                  className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
                  onClick={() => onSelectSession(session.id)}
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
                    onClick={(e) => onDeleteSession(session.id, e)}
                    title="Delete conversation"
                  >×</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

    </aside>
  )
}
