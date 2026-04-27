# Architecture

## Overview

The AI Codebase Understanding Assistant is a RAG (Retrieval Augmented Generation) pipeline that allows users to upload code repositories and ask questions about them.

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: MongoDB (with motor async driver)
- **AI/ML**: OpenAI API (GPT + Embeddings)
- **Frontend**: React + Vite

## Directory Structure

```
backend/
├── api/              # REST endpoints
├── auth/             # Authentication (JWT)
├── models/           # Pydantic models
├── services/         # Business logic
│   ├── processor.py     # Repository processing
│   ├── chunker.py      # Code chunking
│   ├── embedding.py    # OpenAI embeddings
│   ├── vector_store.py # Semantic search
│   ├── keyword_search.py # Text search
│   ├── hybrid_search.py # Combined search
│   ├── llm_service.py # GPT responses
│   └── rag_pipeline.py # Full pipeline
├── middleware/        # Rate limiting, error handlers
└── main.py            # FastAPI app

frontend/
├── src/
│   ├── components/
│   ├── hooks/
│   ├── pages/
│   └── api/
└── public/
```

## Data Flow

1. User uploads ZIP file → `POST /api/repositories`
2. Repository processed → AST parsing, chunking
3. Chunks embedded → OpenAI embeddings stored in MongoDB
4. User asks question → Semantic + Keyword search
5. Results fed to LLM → GPT generates answer

## Database Schema

### Collections

- `users` - User accounts
- `repositories` - Uploaded repositories
- `chunks` - Code chunks with embeddings
- `chat_sessions` - Chat history