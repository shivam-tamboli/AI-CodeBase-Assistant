import { useState } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = 'http://localhost:8000'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [isRegistering, setIsRegistering] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [repositories, setRepositories] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadStatus, setUploadStatus] = useState('')

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

  const fetchRepositories = async (authToken) => {
    try {
      const res = await axios.get(`${API_URL}/repositories`, {
        headers: { Authorization: `Bearer ${authToken}` }
      })
      setRepositories(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const handleUpload = async () => {
    if (!uploadFile) return
    setLoading(true)
    setUploadStatus('Uploading...')
    
    const formData = new FormData()
    formData.append('file', uploadFile)
    
    try {
      const res = await axios.post(`${API_URL}/repositories/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      })
      setUploadStatus('Uploaded! Processing...')
      fetchRepositories(token)
      alert('Repository uploaded successfully!')
      setUploadStatus('')
    } catch (err) {
      setUploadStatus('Upload failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const askQuestion = async () => {
    if (!question || !selectedRepo) return
    setLoading(true)
    setAnswer('')
    setSources([])
    
    try {
      const res = await axios.post(`${API_URL}/chat/query`, {
        question,
        repository_id: selectedRepo,
        limit: 5
      }, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setAnswer(res.data.answer)
      setSources(res.data.sources)
    } catch (err) {
      setAnswer('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="app">
        <header>
          <h1>AI Codebase Assistant</h1>
          <p>Ask questions about your code</p>
        </header>
        <main>
          <div className="login-form">
            <h2>{isRegistering ? 'Register' : 'Login'}</h2>
            <input 
              type="text" 
              placeholder="Username" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input 
              type="password" 
              placeholder="Password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button 
              onClick={isRegistering ? register : login}
              disabled={!username || !password}
            >
              {isRegistering ? 'Register' : 'Login'}
            </button>
            <p className="toggle-auth">
              {isRegistering ? 'Already have an account?' : "Don't have an account?"}
              <button 
                className="link-btn"
                onClick={() => setIsRegistering(!isRegistering)}
              >
                {isRegistering ? ' Login' : ' Register'}
              </button>
            </p>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="app">
      <header>
        <h1>AI Codebase Assistant</h1>
        <button className="logout-btn" onClick={() => { setToken(''); localStorage.removeItem('token') }}>
          Logout
        </button>
      </header>
      
      <main>
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

        <section className="chat-section">
          <h2>Ask Questions</h2>
          
          <div className="repo-select">
            <label>Select Repository:</label>
            <select 
              value={selectedRepo} 
              onChange={(e) => setSelectedRepo(e.target.value)}
            >
              <option value="">-- Select --</option>
              {repositories.map(repo => (
                <option key={repo.id} value={repo.id}>{repo.name}</option>
              ))}
            </select>
          </div>
          
          <div className="question-input">
            <textarea
              placeholder="Ask a question about your code..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
            />
            <button onClick={askQuestion} disabled={loading || !question || !selectedRepo}>
              {loading ? 'Thinking...' : 'Ask'}
            </button>
          </div>
          
          {answer && (
            <div className="answer">
              <h3>Answer:</h3>
              <p>{answer}</p>
              
              {sources.length > 0 && (
                <div className="sources">
                  <h4>Sources:</h4>
                  <ul>
                    {sources.map((src, i) => (
                      <li key={i}>
                        <code>{src.file_path}</code> 
                        (lines {src.start_line}-{src.end_line})
                        <span className="score">{src.score?.toFixed(2)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App