# AI Codebase Understanding Assistant (Advanced)

## Overview

An AI-powered system that enables developers to upload or connect to a repository and ask natural language questions about their codebase. The system utilizes a Retrieval Augmented Generation (RAG) pipeline to retrieve relevant code segments and generate contextual explanations with precise source citations.

---

## Problem Statement

Developers frequently face significant challenges when working with large or unfamiliar codebases:

- **Missing Documentation**: Codebases often lack comprehensive documentation
- **Outdated Information**: Existing documentation may be stale or misleading
- **Scattered Knowledge**: Important context is spread across multiple files and locations
- **Slow Onboarding**: New developers spend excessive time understanding existing code
- **Debugging Difficulty**: Tracing issues across interconnected files is time-consuming

These challenges directly impact developer productivity, increase time-to-onboarding, and slow down feature development and bug fixes.

---

## Solution

Build an intelligent question-answering system that understands your codebase at a deep level. Developers can:

1. Upload a ZIP archive or connect via GitHub (public/private repositories)
2. Ask questions in natural language about their code
3. Receive contextual answers with exact file and line references
4. Understand code flow across multiple files
5. Visualize file dependencies
6. Search for specific functions and their usages

---

## Core Features

### 1. Codebase Upload

- **ZIP Upload**: Drag and drop a ZIP file containing the repository
- **GitHub Integration**: Connect directly to GitHub to fetch repositories
  - Public repositories
  - Private repositories (via OAuth or Personal Access Token)

### 2. Question Answering via Chat Interface

- Natural language queries about the codebase
- Contextual responses that understand code semantics
- Follow-up questions supported (persistent chat memory)
- Code snippets in responses with syntax highlighting

### 3. Source Citations

- Every answer includes references to the source code
- File path and specific line numbers provided
- Clickable links to navigate to the exact location
- Traceability for verification and further exploration

---

## Advanced Features

### 1. Code Flow Explanation

- Trace execution paths across multiple files
- Understand how functions connect and interact
- Identify calling relationships and data flow
- Explain complex interactions in simple terms

### 2. File Dependency Graph

- Visual representation of file relationships
- Node-edge representation showing imports and dependencies
- Identify circular dependencies and potential issues
- Understand architectural patterns

### 3. Function-Level Search

- Search by function name across entire codebase
- Find all usages and definitions
- Understand function signatures and return types
- Locate test files and related utilities

### 4. Persistent Chat Memory

- Store conversation history in MongoDB Atlas
- Resume conversations across sessions
- Track context over multiple interactions
- Associate chats with specific repositories

### 5. GitHub Integration

- **OAuth Authentication**: Secure login with GitHub credentials
- **Personal Access Token**: Optional manual token entry
- **Repository Selection**: Browse and select from user's repositories
- **Automatic Sync**: Pull latest changes on demand

### 6. Multi-File Reasoning

- Synthesize information from multiple source files
- Cross-reference related components
- Build comprehensive answers from scattered code segments
- Handle complex architectural questions spanning many files

---

## Tech Stack

### Backend

- **Language**: Python 3.10+
- **Framework**: FastAPI
  - High-performance async API
  - Automatic API documentation (Swagger UI)
  - Type validation with Pydantic
- **Key Libraries**:
  - `langchain` - LLM orchestration and RAG pipeline
  - `openai` - GPT models for embeddings and generation
  - `pymongo` - MongoDB client
  - `github` - GitHub API integration
  - `gitpython` - Git operations
  - `ast` - Python code parsing

### Frontend

- **Framework**: React 18+
- **Build Tool**: Vite
- **State Management**: React Context + Hooks
- **Styling**: Tailwind CSS
- **UI Components**: Custom components with Lucide icons

### Database

- **MongoDB Atlas** (Primary data store)
  - Document storage for metadata
  - Vector search for semantic similarity
  - Full-text search for keyword matching
  - Persistent storage for chat history

### AI/ML

- **Embeddings**: OpenAI `text-embedding-3-small` model
  - 1536-dimensional vectors
  - Semantic code understanding
- **LLM**: OpenAI GPT-4 or GPT-3.5 Turbo
  - Contextual answer generation
  - Code explanation and summarization

### Authentication

- **GitHub OAuth**: Primary authentication method
- **Session Management**: JWT tokens with expiration
- **Secure Token Handling**: HTTP-only cookies

---

## Search Strategy: Hybrid Search

### What is Hybrid Search?

The system combines two complementary search strategies:

1. **Semantic Search (Vector Similarity)**
   - Converts code chunks into numerical embeddings
   - Uses cosine similarity to find semantically similar code
   - Understands the *meaning* behind code, not just keywords

2. **Keyword Search (BM25/Term Frequency)**
   - Traditional text-based matching
   - Matches exact terms and phrases
   - Indexes file names, function names, class names

### Why Hybrid Search?

Pure semantic search has limitations:
- May miss exact keyword matches
- Can return semantically similar but irrelevant code
- Sensitive to embedding quality

Pure keyword search has limitations:
- Cannot handle synonyms or related terms
- Ignores code context and semantics
- Fails on concept-based queries

Hybrid search combines both:
- **Precision**: Keyword matching ensures exact term presence
- **Recall**: Semantic matching finds related concepts
- **Robustness**: One method compensates for the other's weaknesses

### Implementation

```
Query → Hybrid Retriever → Ranked Results → LLM
         ↓                    ↑
    [Vector Search]      [Keyword Search]
         ↓                    ↓
    [MongoDB Atlas]     [MongoDB Atlas]
       Vector Index      Text Index
```

The hybrid retriever:
1. Executes both search strategies in parallel
2. Uses reciprocal rank fusion to combine results
3. Reranks based on relevance score
4. Returns top-k most relevant code chunks

---

## RAG Pipeline: Detailed Explanation

Retrieval Augmented Generation (RAG) combines information retrieval with LLM generation for accurate, contextual answers.

### Step 1: Code Ingestion

```
Repository → Download/Upload → Local Copy
```

- **ZIP Upload**: Extracted to temporary storage
- **GitHub Clone**: Using GitHub API or git clone
- **Supported Formats**: Any text-based code files

### Step 2: Parsing (AST Analysis)

```
Code Files → AST Parser → Structured Metadata
```

- **File Type Detection**: Identify language (Python, JS, etc.)
- **AST Parsing**: Extract functions, classes, imports
- **Metadata Extraction**:
  - Function names and signatures
  - Class definitions and inheritance
  - Import statements
  - Comments and docstrings
  - Line numbers

### Step 3: Chunking Strategy

```
Parsed Code → Intelligent Chunker → Code Chunks
```

**Chunking Rules**:
- **Maximum Chunk Size**: 1000 tokens
- **Overlap**: 100 tokens between chunks for context continuity
- **Split Points**:
  - Function boundaries
  - Class boundaries
  - Logical sections (imports, constants, main logic)
- **Preserve Context**: Include surrounding code for context

**Example**:
```python
# Original function (150 lines) → 2 chunks
# Chunk 1: Function signature + first 80 lines
# Chunk 2: Last 70 lines + function end
```

### Step 4: Embedding Generation

```
Code Chunks → OpenAI Embedding Model → Vectors
```

- **Model**: `text-embedding-3-small`
- **Dimensions**: 1536
- **Process**:
  1. Take each code chunk
  2. Convert to semantic vector
  3. Store alongside original text
- **Cost**: Pay per token (input only)

### Step 5: Storage in MongoDB Atlas

```
Vectors + Metadata → MongoDB Atlas → Indexed Storage
```

**MongoDB Collections**:
1. **`code_chunks`**: Stores embedded code
   - `_id`: Unique identifier
   - `repository_id`: Parent repository
   - `file_path`: Source file path
   - `content`: Code text
   - `embedding`: 1536-dim vector
   - `metadata`: {start_line, end_line, chunk_type, language}
   - `vector_search_index`: For semantic search
   - `text_index`: For keyword search

2. **`repositories`**: Repository metadata
3. **`chat_sessions`**: Conversation history
4. **`users`**: User accounts and preferences

### Step 6: Hybrid Retrieval

```
User Query → Hybrid Search → Relevant Chunks
```

1. **Query Embedding**: Convert user question to vector
2. **Vector Search**: Find semantically similar chunks (top 20)
3. **Keyword Search**: Find chunks with matching terms (top 20)
4. **Score Fusion**: Combine and rerank results
5. **Context Window**: Select top-k most relevant chunks

### Step 7: LLM Response Generation

```
Relevant Chunks + Query → LLM → Generated Answer
```

**Prompt Engineering**:
```
You are an expert code analyst. Based on the following code context,
answer the user's question. Include file paths and line numbers in your response.

Context:
---
{retrieved_chunks}
---

Question: {user_query}

Answer:
```

**Response Generation**:
- **Model**: GPT-4 (or GPT-3.5 Turbo)
- **Temperature**: 0.2 (controlled creativity)
- **Max Tokens**: 2000
- **System Prompt**: Code analysis specialist

### Step 8: Source Citation Generation

```
LLM Response → Citation Extractor → Source References
```

- **Tracking**: Each retrieved chunk includes source metadata
- **Format**: `[filename:start_line-end_line]`
- **Validation**: Verify citations exist in retrieved context
- **Presentation**: Numbered references in final response

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (React)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Upload    │  │   Chat UI   │  │  Dependency │  │  Settings   │      │
│  │   Component │  │  Interface  │  │    Graph    │  │   Panel     │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
└─────────┼────────────────┼────────────────┼────────────────┼──────────────┘
          │                │                │                │
          └────────────────┴────────┬────────┴────────────────┘
                                   │ HTTP/WebSocket
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (FastAPI)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API Routes                                  │   │
│  │  /auth/*  /repos/*  /upload/*  /chat/*  /search/*  /graph/*       │   │
│  └────────────────────────────────┬────────────────────────────────────┘   │
│                                   │                                         │
│  ┌─────────────┐  ┌─────────────┐  │  ┌─────────────┐  ┌─────────────┐     │
│  │   Auth      │  │  Repository │  │  │   Chat     │  │   Search    │     │
│  │   Service   │  │   Service   │  │  │   Service  │  │   Service   │     │
│  └──────┬──────┘  └──────┬──────┘  │  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼──────────┼──────────┼────────────────┼──────────┘
           │                │          │          │                │
           ▼                ▼          ▼          ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING LAYER                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   GitHub    │  │    ZIP     │  │    AST      │  │    RAG      │         │
│  │   Client    │  │   Parser   │  │   Parser    │  │   Pipeline  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SERVICES                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │   MongoDB Atlas │  │   OpenAI API    │  │   GitHub API    │            │
│  │  (DB + Vector)  │  │(Embeddings+LLM) │  │  (Repositories) │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

**Frontend (React)**
- SPA application served by FastAPI
- Real-time chat updates via polling
- File upload with progress tracking
- Interactive dependency visualization

**Backend (FastAPI)**
- RESTful API endpoints
- Async request handling
- Request validation and error handling
- CORS and security middleware

**Processing Layer**
- Code ingestion from multiple sources
- AST-based code parsing
- RAG pipeline orchestration
- Background task processing

**MongoDB Atlas**
- Primary document database
- Vector search index for semantic queries
- Text index for keyword search
- User data and session storage

**OpenAI API**
- Embedding generation for code chunks
- LLM for answer generation
- Semantic understanding of code

**GitHub API**
- Repository listing and cloning
- OAuth authentication
- File content retrieval

---

## Data Flow: Step-by-Step

### Phase 1: Repository Upload

```
1. User initiates upload
   ├── ZIP: User selects file → Upload to server → Extract to temp
   └── GitHub: OAuth login → List repositories → Select repo → Clone
        │
        ▼
2. Code processing begins
   ├── Scan directory recursively
   ├── Filter by file extensions (.py, .js, .ts, .go, etc.)
   └── Skip: node_modules, __pycache__, .git, etc.
        │
        ▼
3. Parse each file
   ├── Read file content
   ├── Generate AST (for Python) or parse structure
   ├── Extract functions, classes, imports
   └── Store metadata (line numbers, signatures)
        │
        ▼
4. Chunk code intelligently
   ├── Split at function/class boundaries
   ├── Apply size limits (1000 tokens)
   ├── Add overlap for context (100 tokens)
   └── Preserve code formatting
        │
        ▼
5. Generate embeddings
   ├── Send each chunk to OpenAI
   ├── Receive 1536-dim vector
   └── Store with chunk metadata
        │
        ▼
6. Store in MongoDB
   ├── Create vector index
   ├── Create text index
   ├── Link to repository ID
   └── Mark processing complete
```

### Phase 2: User Query

```
1. User sends question
   ├── Input in chat interface
   └── Sanitize and validate
        │
        ▼
2. Query processing
   ├── Convert question to embedding
   ├── Extract keywords for keyword search
   └── Prepare retrieval request
        │
        ▼
3. Hybrid retrieval
   ├── Vector search: Top 20 semantically similar
   ├── Keyword search: Top 20 exact matches
   ├── Combine using reciprocal rank fusion
   └── Rerank by relevance score
        │
        ▼
4. Context preparation
   ├── Take top-k chunks (k=5-10)
   ├── Format with file path and line numbers
   ├── Ensure context window within LLM limits
   └── Add system instructions
        │
        ▼
5. LLM generation
   ├── Send prompt with context + question
   ├── Receive generated answer
   └── Parse and validate response
        │
        ▼
6. Response delivery
   ├── Format with markdown (code blocks, bold)
   ├── Add source citations [file:lines]
   ├── Stream response to client (if long)
   └── Store in chat history
        │
        ▼
7. User sees answer
   ├── Rendered markdown in UI
   ├── Clickable source links
   └── Option to ask follow-up
```

---

## Security

### API Keys and Secrets

- **Environment Variables**: All sensitive config via `.env` file
  - `OPENAI_API_KEY`: OpenAI API key
  - `MONGODB_URI`: MongoDB Atlas connection string
  - `GITHUB_CLIENT_ID`: GitHub OAuth app ID
  - `GITHUB_CLIENT_SECRET`: GitHub OAuth app secret
  - `JWT_SECRET`: Session token signing key

### GitHub OAuth

1. **Authorization Flow**:
   - User clicks "Login with GitHub"
   - Redirect to GitHub OAuth authorization page
   - User approves → GitHub sends authorization code
   - Backend exchanges code for access token
   - Access token used to fetch user info and repos

2. **Token Handling**:
   - Access token stored in session (encrypted)
   - Not stored in database long-term
   - Refresh tokens when possible
   - Revoke tokens on logout

3. **Private Repository Access**:
   - OAuth scope: `repo` (read-only access)
   - Token used only for repository operations
   - Token cleared after successful clone

### Data Privacy

- **Code Processing**: Code temporarily stored during processing
- **Embeddings**: Stored in MongoDB (user's project)
- **Chat History**: Only stored with user consent
- **No External Sharing**: Code not sent to third parties

### Rate Limiting

- OpenAI API calls rate-limited per user
- MongoDB queries optimized to prevent timeouts
- File upload size limits enforced

---
