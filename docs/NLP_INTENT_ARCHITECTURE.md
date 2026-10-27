# Multilingual NLP & Intent Understanding Architecture

## 1. Overview & Separation of Concerns

The NLP pipeline separates acoustic transcription from intent comprehension and security validation:

```
  SPEECH
    ↓
  TRANSCRIPT (raw_text preserved verbatim)
    ↓
  LANGUAGE DETECTION (en, te, te-en)
    ↓
  INTENT UNDERSTANDING (Gemini structured output or rule engine)
    ↓
  STRUCTURED INTENT (Pydantic model)
    ↓
  SECURITY VALIDATION (ALLOW, DENY, REQUIRES_CONFIRMATION)
    ↓
  AGENT DELEGATION (Miss Minutes ↔ Jarvis)
    ↓
  TYPED CAPABILITY (Allowlisted action)
```

## 2. Intent Schema (`intents/schema.py`)

### `IntentType` Enum
- `CHAT`: General conversational chit-chat / banter.
- `QUESTION`: Factual or informational inquiry.
- `SEARCH_WEB`: General web search query.
- `OPEN_WEBSITE`: Opening an approved website URL.
- `OPEN_APP`: Launching an approved desktop application.
- `PLAY_MEDIA`: Media playback (e.g. YouTube music).
- `GET_TIME`: Querying system clock and date.
- `GET_SYSTEM_STATUS`: System CPU/RAM/OS status.
- `GET_BATTERY_STATUS`: Battery and charging status.
- `GET_VOLUME`: Current master volume level.
- `SET_VOLUME`: Master audio volume adjustment (requires confirmation).
- `DELEGATE_TO_JARVIS`: Explicit task delegation to Jarvis.
- `DELEGATE_TO_MISS_MINUTES`: Explicit user-facing response delegation.
- `CANCEL`: Cancellation of active operation.
- `UNKNOWN`: Unclassifiable input.

### `StructuredIntent` Model
```python
class StructuredIntent(BaseModel):
    intent: IntentType
    language: LanguageCode          # 'en', 'te', 'te-en', 'unknown'
    raw_transcript: str            # Verbatim user input
    confidence: float              # 0.0 to 1.0
    entities: IntentEntities       # Extracted typed entities
    requires_action: bool          # True if desktop action is needed
    preferred_agent: str           # 'miss_minutes' or 'jarvis'
    reasoning: Optional[str]
```

## 3. Multilingual & Code-Switching Principles

The system natively supports:
1. **English**: e.g., `"Open YouTube."`, `"Play some music."`, `"What is quantum computing?"`, `"Open Chrome."`
2. **Telugu**: e.g., `"YouTube open cheyyi."`, `"Oka paata play cheyyi."`, `"Quantum computing ante enti?"`
3. **Telugu-English Code-Switching (`te-en`)**: e.g., `"YouTube open chesi AR Rahman songs play cheyyi."`, `"Chrome open cheyyi."`, `"Naaku quantum computing explain cheyyi."`

### Critical Rules
- **No Early Forced Translation**: Telugu is **never** pre-translated to English prior to intent parsing. Doing so destroys idiomatic phrasing and intent nuances.
- **Transcript Preservation**: The exact string spoken by the user is retained in `raw_transcript`.
- **Entity Extraction**: App names and websites are normalized to canonical targets (e.g., `"chrome"` -> `"Google Chrome"`, `"youtube"` -> `"https://www.youtube.com"`).

## 4. Parser Architecture (`intents/parser.py`)

The `IntentParser` features dual-engine execution:
1. **AI Mode (When Gemini is active)**: Uses `GeminiProvider.generate_structured` with `INTENT_EXTRACTION_SYSTEM_PROMPT` to parse complex syntax and semantic entities into `StructuredIntent`.
2. **Deterministic Fallback Engine**: Employs linguistic token matching and regex patterns for English, Telugu, and mixed utterances. Ensures full testability, offline reliability, and zero-API-key functionality.
