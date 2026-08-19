# Provider Architecture

The AI Codebase Assistant is decoupled from any specific AI vendor. LLM completions and vector embeddings are provided through abstract interfaces — switching providers requires only environment variable changes, no code modifications.

---

## Interfaces

Two abstract base classes live in `backend/services/providers/base.py`:

### `LLMProvider`

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> str: ...

    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]: ...
```

The canonical message format is provider-neutral:
- `system: str` — the instruction/system prompt
- `messages: list[dict]` — alternating `{"role": "user"|"assistant", "content": "..."}` turns

Concrete providers translate to their SDK's native format internally.

### `EmbeddingProvider`

```python
class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]: ...

    async def embed_one(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]
```

`embed_one` is a concrete convenience method — subclasses only need to implement `embed_batch`.

---

## Implementations

### OpenAI LLM (`openai_provider.py`)

- Uses `AsyncOpenAI` (async client, single instance)
- System prompt is prepended as `{"role": "system", "content": system}` in the messages array (OpenAI's native format)
- `complete()` calls `client.chat.completions.create()` and returns `response.choices[0].message.content`
- `stream()` uses `create(stream=True)` and yields `chunk.choices[0].delta.content` for each event

### Anthropic Claude (`anthropic_provider.py`)

- Uses `AsyncAnthropic` (async client, single instance)
- `system` is a top-level parameter in `client.messages.create()` — not part of the messages array
- `complete()` returns `response.content[0].text`
- `stream()` uses `async with client.messages.stream(...) as stream:` context manager and yields from `stream.text_stream`

**Note on API shape differences**: OpenAI and Anthropic have different API shapes. The provider layer handles this translation so `LLMService` doesn't need to know which provider is in use.

### OpenAI Embeddings (`openai_provider.py`)

- Model: `text-embedding-3-small` (default) — 1536 dimensions
- `embed_batch()` batches texts in groups of ≤ 2,000 (OpenAI API hard limit)
- Retry logic: exponential backoff (1s → 2s → 4s) on `RateLimitError` (429) and `APIStatusError` 5xx
- Single `AsyncOpenAI` client instance shared across all batches

---

## Factory

`backend/services/providers/factory.py` provides two functions that route to the correct implementation based on environment variables:

```python
def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic")
        return AnthropicLLMProvider(api_key=api_key, model=model)

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER=openai")
        return OpenAILLMProvider(api_key=api_key, model=model)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingProvider(api_key=api_key, model=model)

    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")
```

Providers are instantiated **once at application startup** via FastAPI's lifespan function and stored on `app.state`. Route handlers retrieve them from `request.app.state.*` — no per-request construction.

---

## Configuration

| Variable | Default | Options |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai`, `anthropic` |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI: `gpt-4o-mini`, `gpt-4o`, `gpt-4` · Anthropic: `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, `claude-opus-4-7` |
| `EMBEDDING_PROVIDER` | `openai` | `openai` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | `text-embedding-3-small` (1536-dim), `text-embedding-3-large` (3072-dim) |
| `OPENAI_API_KEY` | — | Required for OpenAI LLM and/or embeddings |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |

**Cost guidance:**
- `gpt-4o-mini`: $0.15 / 1M input tokens — recommended for development and demos
- `text-embedding-3-small`: $0.02 / 1M tokens — very cheap; a 500-file repo typically uses < 200K tokens
- `claude-haiku-4-5`: Fast and cheap — comparable to `gpt-4o-mini`
- `claude-sonnet-4-6`: Higher quality, higher cost — comparable to `gpt-4o`

---

## Adding a New LLM Provider

1. **Implement the interface** in a new file `backend/services/providers/your_provider.py`:

```python
from backend.services.providers.base import LLMProvider
from typing import AsyncIterator, List

class YourLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self._client = YourSDKAsyncClient(api_key=api_key)
        self._model = model

    async def complete(
        self, system: str, messages: List[dict],
        max_tokens: int = 2000, temperature: float = 0.2
    ) -> str:
        # translate system + messages to your SDK's format
        response = await self._client.generate(
            system=system,
            messages=messages,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.text   # adapt to your SDK's response shape

    async def stream(
        self, system: str, messages: List[dict],
        max_tokens: int = 2000, temperature: float = 0.2
    ) -> AsyncIterator[str]:
        async with self._client.stream(
            system=system, messages=messages,
            model=self._model, max_tokens=max_tokens,
        ) as stream:
            async for token in stream.text_stream:
                yield token
```

2. **Register in the factory** (`backend/services/providers/factory.py`):

```python
if provider == "yourprovider":
    api_key = os.getenv("YOUR_API_KEY")
    if not api_key:
        raise ValueError("YOUR_API_KEY is required when LLM_PROVIDER=yourprovider")
    return YourLLMProvider(api_key=api_key, model=model)
```

3. **Add to `.env.example`**:

```env
# Required when LLM_PROVIDER=yourprovider
YOUR_API_KEY=
```

4. **Write tests** covering `complete()` and `stream()` with a mocked client. See `backend/tests/conftest.py` for the existing mock patterns.

---

## How Services Use Providers

`LLMService` and `EmbeddingService` accept an optional `provider` argument in their constructors — if omitted, the factory is called automatically:

```python
class LLMService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self._provider = provider or get_llm_provider()

class EmbeddingService:
    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider or get_embedding_provider()
```

This allows tests to inject a mock provider without touching environment variables, and allows the factory to remain the single source of truth for production instantiation.
