# AI Provider Architecture — Miss Minutes + Jarvis

## 1. Overview & Architectural Principles

The intelligence layer for Miss Minutes + Jarvis is designed around a strict provider abstraction boundary.
No code in the user interface, speech service, or capability layer communicates directly with vendor-specific LLM SDKs. All reasoning, dialogue generation, and structured intent extraction pass through the unified `AIProvider` contract.

```
       ┌─────────────────────────────────────────────────────┐
       │             Miss Minutes & Jarvis Agents            │
       └──────────────────────────┬──────────────────────────┘
                                  │
                                  ▼
       ┌─────────────────────────────────────────────────────┐
       │              AIProvider Base Protocol               │
       │  - generate_response(prompt, config)                │
       │  - generate_structured(prompt, schema, config)      │
       │  - is_available() -> bool                           │
       └──────────┬───────────────────┬───────────────────┬──┘
                  │                   │                   │
                  ▼                   ▼                   ▼
       ┌────────────────────┐ ┌───────────────┐ ┌────────────────┐
       │   GeminiProvider   │ │ GroqProvider  │ │ MockAIProvider │
       │ (Official GenAI SDK│ │  (OpenAI SDK  │ │(Deterministic, │
       │   google-genai)    │ │   Fallback)   │ │  Zero-Network) │
       │     PRIMARY        │ │   SECONDARY   │ │    TESTING     │
       └────────────────────┘ └───────────────┘ └────────────────┘
```

## 2. Locked Technology Stack

### Primary: Google Gemini (`google-genai`)
- **SDK**: Official Google GenAI Python SDK (`google-genai` v1.73.1).
- **Default Model**: `gemini-2.5-flash`.
- **Structured Output**: Native `GenerateContentConfig(response_mime_type="application/json", response_schema=...)`.
- **Role**: Primary conversational reasoning, Telugu and English understanding, code-switching comprehension, and tool planning.
- **Fail-Safe**: If `GEMINI_API_KEY` is not configured, `is_available()` returns `False`. The provider never throws uncaught SDK exceptions into the application lifecycle.

### Fallback: Groq (`openai` compatible client)
- **SDK**: `openai` Python client configured with Groq base URL `https://api.groq.com/openai/v1`.
- **Default Model**: `llama-3.3-70b-versatile`.
- **Role**: Optional fallback provider. The application **never** silently depends on Groq; it operates seamlessly with Gemini alone or in mock mode when Groq is unavailable.

### Mock Provider: `MockAIProvider`
- Deterministic, zero-dependency provider for offline environments, test suites, and zero-API-key mode.
- Records all received prompts for verification.

## 3. Interfaces & Data Contracts

### Core Interface (`ai/provider.py`)
```python
class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def generate_response(
        self, prompt: str, config: Optional[ModelConfig] = None
    ) -> ProviderResponse: ...

    @abstractmethod
    def generate_structured(
        self, prompt: str, response_schema: Type[T], config: Optional[ModelConfig] = None
    ) -> T: ...
```

### Configuration Contract (`ai/provider.py`)
- `ModelConfig`: Specifies `model_name`, `temperature`, `max_tokens`, `system_instruction`, and `stop_sequences`.
- `ProviderResponse`: Returns `content`, `structured_data`, `provider_id`, `model_used`, and `finish_reason`.

## 4. Prompts & Agent Personas (`ai/prompts.py`)

- **Miss Minutes Prompt**: Female, witty, playful, warm, slightly Southern ("Well howdy y'all!"), user companion, Telugu + English awareness, delegates technical operations to Jarvis.
- **Jarvis Prompt**: Male, calm, professional, technically precise, British/formal cadence, capability analyst, security guardian.
- **Intent Extraction Prompt**: Directs LLM to preserve raw transcript verbatim, detect language (`en`, `te`, `te-en`), and emit structured Pydantic models.

## 5. Future Activation Points (Phase 6)

In Phase 6 (Real AI Activation):
1. Supply real API keys in `.env` (`GEMINI_API_KEY=...`).
2. The `IntentParser` automatically detects that `GeminiProvider.is_available() == True` and delegates live semantic extraction to Gemini.
3. Real multi-turn dialogue between Miss Minutes and the user will stream through `GeminiProvider.generate_response`.
