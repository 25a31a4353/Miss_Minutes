# Jarvis Single Implementation Audit & Architecture Correction

## 1. Context & Architectural Mandate

In Phases 1–3, an agent wrapper `agents/jarvis_agent.py` was introduced while the legacy Jarvis files (`jarvis_brain.py`, `jarvis_actions.py`, `jarvis_market.py`, `jarvis_voice.py`) were left untouched. This created an unintended architectural duplication:
- **Two Jarvis representations existed**: the legacy modules in the root directory and the newly created `JarvisAgent` in `agents/`.
- **Duplicated definitions**: `SITES`, `ALIASES`, action regexes, and persona descriptions were re-declared in `agents/jarvis_agent.py`.
- **Fragmented ownership**: It was ambiguous which module was the true authority for Jarvis's intelligence and capability selection.

### Non-Negotiable Architectural Rule
> **COUNT(JARVIS_IMPLEMENTATIONS) = 1**
> There is only ONE Jarvis. We do not build a second Jarvis. We do not wrap the old Jarvis while leaving it permanently untouched.
> The existing Jarvis codebase is the foundation. It must be **modified, refactored, adapted to Windows, secured with Gemini/Pydantic/SecurityValidator, and directly integrated with Miss Minutes**.

---

## 2. Audit of Existing Jarvis Modules

| Module | Original Responsibility | Identified Issues / Technical Debt | Required Migration & Evolution |
| :--- | :--- | :--- | :--- |
| **`jarvis_brain.py`** | Hybrid Groq LLM + local action fallback; rate-limit cooldown handling; system prompt. | Hard-coded to Groq API with OpenAI SDK; no Gemini integration; no Pydantic structured output; no multilingual support. | **Refactor**: Upgrade to use `AIProvider` abstraction (`GeminiProvider` primary, `GroqProvider` fallback, `MockAIProvider` for tests). Add multilingual intent handling, Pydantic capability extraction, and keep dry wit personality and cooldown handling. |
| **`jarvis_actions.py`** | Local deterministic actions: app launch, web routing, WhatsApp, mail brief, volume, date/time. | macOS-specific (`subprocess.run(["open", ...])`, `osascript`, `/Applications` scanning); no security validation layer. | **Refactor**: Strip macOS-specific code; adapt to Windows; convert all action executions into typed `CapabilityRequest` objects; route 100% of actions through `SecurityValidator` and allowlisted executors. Preserve `SITES`, `ALIASES`, market queries, WhatsApp and mail briefing concepts. |
| **`jarvis_market.py`** | Real-time stock market analysis (Yahoo Finance), momentum/SMA calculation, Buy/Sell/Hold signals. | Standalone module with global SSL context; not integrated into unified capability pipeline. | **Preserve & Modernize**: Retain all financial algorithms, ticker maps (`DEFAULT_TICKERS`), and briefing generators; expose clean typed query methods for Jarvis's technical reasoning. |
| **`jarvis_voice.py`** | Continuous microphone listening loop using `speech_recognition`, macOS `say -v Samantha` TTS. | Blocking infinite loop; macOS-specific TTS; no integration with state machine, `edge-tts`, or Miss Minutes voice coordination. | **Refactor**: Remove blocking loop; adapt TTS to shared `voice/` infrastructure using Jarvis's distinct British/formal voice (`en-GB-RyanNeural` / `te-IN-MohanNeural`). |
| **`jarvis.py`** | (New Authoritative Coordinator) | Previously absent as a unified entrypoint. | **Create**: Unified coordinator representing the single authoritative `Jarvis` agent inheriting from `Agent` for message bus communication, directly binding `jarvis_brain`, `jarvis_actions`, `jarvis_market`, and `jarvis_voice`. |

---

## 3. Audit of Duplicated Phase 3 / Phase 4 Components

| Component | Duplication Identified | Resolution Plan |
| :--- | :--- | :--- |
| **`agents/jarvis_agent.py`** | Re-declared `SITES`, `ALIASES`, action regexes, and persona prompt in parallel with `jarvis_actions.py` and `jarvis_brain.py`. | **Consolidate**: Eliminate duplicated logic. Move all authoritative reasoning and action resolution into the existing Jarvis modules (`jarvis_brain.py`, `jarvis_actions.py`) and top-level `jarvis.py`. Update `agents/jarvis_agent.py` to re-export `Jarvis` from `jarvis.py` for backward compatibility. |
| **Action Planning** | `agents/jarvis_agent.py` had a parallel `_handle_delegation` method while `jarvis_actions.py` had `try_action`. | **Consolidate**: Centralize all action resolution in `jarvis_actions.py` and invoke it directly from `jarvis.py` and `jarvis_brain.py`. |

---

## 4. Reusable Shared Infrastructure (Retained)

The following components represent **shared infrastructure** (not Jarvis-specific duplication) and are retained:
- **`agents/base.py`**: Generic `Agent` abstract base class.
- **`agents/message.py`**: Generic `AgentMessage`, `AgentId`, `MessageType`, `Priority` protocols.
- **`agents/bus.py`**: In-memory `AgentMessageBus` providing rate limiting, turn bounding, and message routing.
- **`agents/context.py`**: `SharedBoundedContext` for conversation history.
- **`agents/audit_log.py`**: Immutable conversation audit logging.
- **`agents/miss_minutes_agent.py`**: Miss Minutes agent implementation (distinct female personality).
- **`ai/` layer**: `AIProvider`, `GeminiProvider`, `GroqProvider`, `MockAIProvider`.
- **`intents/` layer**: `StructuredIntent`, `IntentParser`, `IntentEntities`.
- **`security/` layer**: `SecurityValidator`, `SecurityDecision`, `SecurityAuditLogger`.
- **`actions/` layer**: `CapabilityRequest`, `CapabilityResult`, `ActionRegistry`, `MockActionExecutor`.
- **`voice/` layer**: `VoiceService`, `SpeechToTextProvider`, `TextToSpeechProvider`, `WakeWordDetector`.

---

## 5. Final Authoritative Ownership Map

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FINAL OWNERSHIP MAP                             │
├──────────────────────────────┬─────────────────────────────────────────┤
│ Feature                      │ Single Authoritative Implementation     │
├──────────────────────────────┼─────────────────────────────────────────┤
│ Miss Minutes Personality     │ agents/miss_minutes_agent.py            │
│ Jarvis Personality & Brain   │ jarvis_brain.py + jarvis.py             │
│ Jarvis Action Engine         │ jarvis_actions.py                       │
│ Jarvis Market Intelligence   │ jarvis_market.py                        │
│ Jarvis Voice Engine          │ jarvis_voice.py + voice/voices.py       │
│ Agent Communication Bus      │ agents/bus.py (shared infrastructure)   │
│ Security Validation          │ security/validator.py (shared gate)     │
│ Allowlisted Capability Tools │ actions/registry.py + mock_executor.py  │
│ AI Intelligence Providers    │ ai/ (shared infrastructure)             │
│ Speech & Voice Services      │ voice/ (shared infrastructure)          │
└──────────────────────────────┴─────────────────────────────────────────┘
```

---

## 6. Target Interaction Architecture

```text
                         USER
                           │
                           ▼
                    MISS MINUTES
                  (User-facing AI)
                           │
                           │ AgentMessage (DELEGATION)
                           ▼
                 ┌─────────────────┐
                 │ EXISTING JARVIS │
                 │  (jarvis.py)    │
                 │                 │
                 │ ┌─────────────┐ │
                 │ │jarvis_brain │ │
                 │ └─────────────┘ │
                 │ ┌─────────────┐ │
                 │ │jarvis_actions │
                 │ └─────────────┘ │
                 │ ┌─────────────┐ │
                 │ │jarvis_market│ │
                 │ └─────────────┘ │
                 └────────┬────────┘
                          │
                          │ CapabilityRequest
                          ▼
                 SECURITY VALIDATOR  <─── [OFFLINE Gate + Anti-Injection]
                          │
                          │ ALLOW
                          ▼
                 ALLOWLISTED TOOLS
                          │
                          ▼
                   WINDOWS SYSTEM
```

**Single Jarvis Invariant Satisfied**:
There is strictly **ONE** Jarvis implementation in the system, centered in `jarvis.py` and its core modules `jarvis_brain.py`, `jarvis_actions.py`, and `jarvis_market.py`.
