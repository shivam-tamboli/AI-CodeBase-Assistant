# API Flow

## Authentication

### Register
```
POST /api/auth/register
Body: { "username": "string", "password": "string" }
Response: { "message": "User created", "user_id": "string" }
```

### Login
```
POST /api/auth/login
Body: { "username": "string", "password": "string" }
Response: { "access_token": "string", "token_type": "bearer" }
```

## Repositories

### Upload Repository
```
POST /api/repositories/upload
Headers: Authorization: Bearer <token>
Body: multipart/form-data (file: ZIP)
Response: { "id": "string", "name": "string", "status": "processed" }
```

### List Repositories
```
GET /api/repositories
Headers: Authorization: Bearer <token>
Response: [{ "id": "string", "name": "string", ... }]
```

### Get Repository
```
GET /api/repositories/{repo_id}
Headers: Authorization: Bearer <token>
Response: { "id": "string", "name": "string", ... }
```

### Delete Repository
```
DELETE /api/repositories/{repo_id}
Headers: Authorization: Bearer <token>
Response: { "message": "Repository deleted" }
```

## Chat

### Create Session
```
POST /api/chat/sessions
Headers: Authorization: Bearer <token>
Body: { "repository_id": "string" }
Response: { "session_id": "string" }
```

### Send Message
```
POST /api/chat/sessions/{session_id}/messages
Headers: Authorization: Bearer <token>
Body: { "message": "string" }
Response: { "answer": "string", "sources": [...] }
```

### Get History
```
GET /api/chat/sessions/{session_id}/messages
Headers: Authorization: Bearer <token>
Response: [{ "role": "user|assistant", "content": "string" }]
```

## Health

### Health Check
```
GET /health
Response: { "status": "healthy|unhealthy", "database": "connected|disconnected" }
```