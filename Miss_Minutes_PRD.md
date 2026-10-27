# Miss Minutes — Product Requirements Document (PRD)

**Document Status:** Authoritative Product Requirements Document (PRD) — Synchronized through Phase 6  
**Target Platform:** Windows 10/11 (64-bit)  
**Product Type:** Native desktop voice assistant with transparent animated overlay & dual-agent co-pilot  
**Working Name:** Miss Minutes  
**Reference Codebase:** https://github.com/25a31a4353/Jarvis  
**Dual-Agent Partner:** Jarvis (`jarvis.py`)  
**Last Updated:** October 2026  

---

## 1. Product Vision

Build **Miss Minutes**, a polished, personalised, voice-first desktop AI assistant for Windows. It operates as a warm, engaging desktop companion rather than a sterile chatbot: a transparent animated clock-inspired character sits above other windows, listens only when enabled, responds naturally, and coordinates with her technical co-pilot, **Jarvis**, to perform a carefully limited set of user-approved computer actions.

The visual direction is inspired by the retro-futuristic timeline clock aesthetic, utilizing original artwork, expressions, visual state indicators, and animations.

### Dual-Agent Architecture & The Single-Jarvis Invariant
Miss Minutes does not work alone; she is paired with **Jarvis** in a close, collaborative partnership:
- **Miss Minutes:** Female, primary user-facing desktop companion. Warm, witty, playful, curious, slightly mischievous, deeply loyal, and conversational.
- **Jarvis:** Male, technical specialist co-pilot. Calm, professional, technically precise, protective of system security, confident, with a dry British wit.

```text
COUNT(JARVIS_IMPLEMENTATIONS) = 1
```

> [!IMPORTANT]
> The authoritative Jarvis remains the existing Jarvis implementation in the repository (`jarvis.py` with `jarvis_brain.py`, `jarvis_voice.py`, `jarvis_actions.py`, and `jarvis_market.py`). Jarvis is not re-invented, duplicated, or replaced; he is adapted into the dual-agent architecture via the typed `AgentMessageBus`.

---

## 2. Goals

1. **Native Desktop Shell:** Deliver a responsive Windows desktop application built with Python 3.11+ and PySide6, not merely a web demo or HTML wrapper.
2. **Expressive Overlay & Controller:** Provide an attractive, transparent, always-on-top character overlay reacting across 12 distinct visual states, complemented by a persistent controller panel.
3. **Multilingual Understanding:** Support fluent speech interaction in **English**, **Telugu**, and **Telugu-English code-switching** without forcing early translation to English.
4. **Authoritative Master OFFLINE Control:** A clearly visible, user-controlled master ON/OFF switch. When OFF, microphone capture, wake-word detection, speech recognition, AI reasoning, and audio playback are strictly stopped.
5. **Local Wake Phrase:** Recognize the wake phrase **“Hey Minutes”** when enabled, transitioning the assistant into active listening.
6. **Gemini Primary AI Intelligence:** Use Google Gemini (official `google-genai` SDK, model `gemini-2.5-flash`) as the primary intelligence provider, with optional Groq fallback and a deterministic Mock provider behind the `AIProvider` abstraction.
7. **Default DENY Security Allowlist:** Execute only explicitly approved, typed, and validated actions through `SecurityValidator`.
8. **Testability & Observability:** Maintain 100% deterministic test coverage across unit, lifecycle, voice, security, and AI provider suites without requiring live credentials or external network access.
9. **Graceful Fault Tolerance:** Provide seamless failover across AI providers (Gemini → Groq → Mock) and audio hardware fallbacks without crashing or falsifying success.

---

## 3. Non-Goals and Explicit Exclusions

The product is explicitly prohibited from:
- Granting the AI arbitrary, unconstrained control over the operating system.
- Allowing arbitrary shell execution (`cmd.exe`, `powershell.exe`, `pwsh`, `bash`).
- Executing model-generated Python scripts, batch files, or dynamic command strings.
- Reading private files, email, credentials, password vaults, or browser session tokens without explicit, separately authorized user flows.
- Modifying the Windows Registry, disabling antivirus/Windows Defender, elevating privileges, or deleting files.
- Treating wake-word detection as biometric identity verification or authorization.
- Bundling or distributing proprietary third-party commercial assets without licensing.

---

## 4. Target User and Main Use Cases

The primary user is a Windows laptop/desktop user desiring a hands-free, visually engaging companion for productivity, general knowledge, study help, and safe everyday desktop control.

### Primary Use Cases:
1. **Conversational Inquiries:** Ask general questions, study topics, or technical concepts (e.g. *"Explain quantum entanglement"*, *"Quantum entanglement ante enti?"*) and receive natural, concise spoken and visual explanations in the matching language.
2. **Follow-Up Dialogue:** Multi-turn conversational memory (e.g., Turn 1: *"What is quantum entanglement?"* → Turn 2: *"Give me a simple example."*) with bounded context retention.
3. **Technical Delegation to Jarvis:** When the user requests media, system status, or application tasks, Miss Minutes coordinates with Jarvis over the message bus to formulate safe, allowlisted capabilities.
4. **Allowlisted Web & Media Navigation:** Safe browser navigation to approved web targets (Google, YouTube, GitHub, Maps) and search queries (e.g. *"Play AR Rahman songs on YouTube"*).
5. **System Diagnostics:** Checking local time, date, battery level, volume, CPU, and RAM metrics.
6. **Master Privacy Control:** Instant toggle to OFFLINE mode, guaranteeing complete hardware and network silence.

---

## 5. Product Experience and UI Requirements

### 5.1 Desktop Shell
- Native PySide6 frameless, translucent window with custom SVG/vector rendering.
- Always-on-top behavior with automatic multi-monitor boundary clamping (`clamp_to_screen_boundaries`).
- Position persistence saved to `~/.miss_minutes/config.json`.
- Reduced-motion mode for accessibility, disabling high-frequency facial animations.
- Independent, toggleable Miss Minutes Controller surface exposing status, volume, settings, and diagnostic demos.

### 5.2 The 12 Authoritative Interaction States
The assistant transitions through an explicit, testable finite state machine (`AppStateMachine`):
- `OFFLINE` — System completely disabled; microphone, wake detection, and AI strictly halted.
- `IDLE` — Online and standing by; listening for the "Hey Minutes" wake phrase.
- `WAKE_DETECTED` — Wake phrase recognized; acknowledging user presence.
- `LISTENING` — Active microphone phrase capture.
- `TRANSCRIBING` — Converting audio to text via `faster-whisper`.
- `THINKING` — Natural language understanding, Gemini reasoning, and dual-agent delegation.
- `VALIDATING` — Capability request evaluated by `SecurityValidator` against the allowlist.
- `WORKING` — Approved capability in progress.
- `SPEAKING` — Delivering TTS audio response through system speakers.
- `SUCCESS` — Action confirmed and successfully completed.
- `ERROR` — Operational error encountered with informative feedback.
- `BLOCKED` — Security validator refused an unapproved or unsafe operation.

---

## 6. Voice and Conversation Architecture

```text
Microphone (WASAPI)
        ↓
Acoustic Wake Detector ("Hey Minutes")
        ↓
Miss Minutes → LISTENING
        ↓
faster-whisper STT (int8 CPU tiny model)
        ↓
Verbatim Transcript (en / te / te-en)
        ↓
Resilient AI Provider (Gemini primary)
        ↓
Dual-Agent Delegation (Miss Minutes ↔ Jarvis)
        ↓
Response Synthesis
        ↓
TTS (edge-tts / Windows SAPI)
        ↓
Speaker (QMediaPlayer / winsound)
```

### 6.1 Microphone & Capture (`voice/microphone.py`)
- Explicit device management via `QMediaDevices` / `AudioDeviceManager`.
- Timeout guards and silence detection preventing infinite blocking loops.
- Deterministic audio injection interfaces for automated tests.
- Immediate resource release when transitioning to `OFFLINE`.

### 6.2 Wake Word (`voice/wake.py`)
- Local acoustic detector for the phrase **“Hey Minutes”**.
- Non-authenticating: only signals the assistant to begin listening; never grants permissions.

### 6.3 Speech-to-Text (`voice/stt.py`)
- Powered by `faster-whisper` (1.2.1) using the locally cached `Systran/faster-whisper-tiny` model.
- Native transcription for English, Telugu, and mixed code-switching.
- Verbatim transcript preservation without forced translation to English.
- Silence activity guard: silence or empty audio never triggers action capabilities.

### 6.4 Text-to-Speech & Playback (`voice/tts.py`, `voice/audio_player.py`)
- Shared voice coordinator supporting distinct agent voice profiles:
  - **Miss Minutes:** Cheerful Southern cadence (`en-US-JennyNeural`, `te-IN-ShrutiNeural`).
  - **Jarvis:** Executive British cadence (`en-GB-RyanNeural`, `te-IN-MohanNeural`).
- Non-blocking asynchronous playback via `QMediaPlayer` / `QAudioOutput` with `winsound` fallback.
- Automatic deletion of temporary speech audio files.

---

## 7. AI Provider Architecture

```text
AIProvider
  ├── GeminiProvider (Primary: official google-genai SDK, gemini-2.5-flash)
  ├── GroqProvider (Secondary: OpenAI-compatible Groq API)
  └── MockAIProvider (Tertiary: 100% deterministic offline test provider)
```

### 7.1 Configuration & Secret Management
- `GEMINI_API_KEY`: Configured via OS environment or local `.env`.
- `GEMINI_MODEL`: Configurable model identifier (default `gemini-2.5-flash`).
- `MAX_CONVERSATION_TURNS`: Bounded memory limit (default `10` turns).
- `.gitignore` strictly protects `.env`, `*.key`, and credentials. Zero plain-text secrets in repository.

### 7.2 Conversational Reasoning & Streaming
- Bounded multi-turn memory (`SharedBoundedContext`) maintaining contextual continuity for follow-up questions.
- Built-in streaming support (`generate_content_stream`) for low-latency dialogue.
- Structured JSON outputs mapped to Pydantic schemas (`StructuredIntent`, `AgentDialogueResponse`).

### 7.3 Multi-Provider Failover (`ai/fallback_provider.py`)
- `ResilientAIProvider` orchestrates seamless failover from Gemini to Groq or Mock upon HTTP 429 rate limits, quota exhaustion, or network disconnects without crashing the desktop UI.

---

## 8. Security & Permission Model (Release-Critical)

```text
Speech / Text Utterance
          ↓
  faster-whisper STT
          ↓
    AI Provider
          ↓
  Structured Intent
          ↓
 CapabilityRequest (Typed schema)
          ↓
 SecurityValidator (ALLOW / DENY / CONFIRM)
          ↓
    Allowlist Check (Default DENY)
          ↓
 Typed Action Executor (Mocked in Phase 6; Live in Phase 7)
          ↓
 UI Feedback & TTS Confirmation
```

### 8.1 Action Validation Rules
- **Default Posture:** DENY by default.
- **Strict Typing:** Commands must conform to `CapabilityRequest` with validated parameters.
- **Pattern Matching:** Forbidden pattern regex instantly blocks shell commands (`powershell`, `pwsh`, `cmd.exe`, `del`, `format`, `reg`, `rmdir`).
- **Confirmation Gate:** High-impact operations require explicit user confirmation through UI buttons before execution.

---

## 9. Existing Jarvis Repository: Single-Implementation Mandate

```text
jarvis.py
  ├── jarvis_brain.py (AI reasoning, cooldown, fallback)
  ├── jarvis_voice.py (Executive voice profile)
  ├── jarvis_actions.py (Capability planning & URL routing)
  └── jarvis_market.py (Yahoo Finance market analytics)
```

The repository maintains **exactly one Jarvis implementation**. Miss Minutes communicates with this authoritative implementation via typed `AgentMessage` objects over the `AgentMessageBus`. `agents/jarvis_agent.py` functions exclusively as a dynamic proxy wrapper around `jarvis.py`.

---

## 10. Phased Implementation Status

```text
[PHASE 0] Discovery & Repository Audit       ──► [COMPLETED]
[PHASE 1] Safe Desktop Foundation            ──► [COMPLETED]
[PHASE 2] Visuals, UX & State Machine        ──► [COMPLETED]
[PHASE 3] Dual-Agent Foundation              ──► [COMPLETED]
[PHASE 4] Capability Architecture & Security  ──► [COMPLETED]
[CORRECT] Single-Jarvis Architectural Fix    ──► [COMPLETED]
[PHASE 5] Real Voice Layer (Mic, STT, TTS)   ──► [COMPLETED]
[PHASE 6] Live Gemini Intelligence           ──► [COMPLETED]
[PHASE 7] Secure Real Windows Capabilities    ──► [COMPLETED]
[PHASE 8] Production Consolidation & Readiness──► [COMPLETED]
[PHASE 9] Security & Production Hardening    ──► [COMPLETED]
[PHASE 10] Windows EXE Packaging & Installer ──► [COMPLETED]
```

### Details by Phase:
- **Phase 0–3:** Desktop lifecycle, PySide6 overlay, 12-state UI machine, dual-agent bus, and position persistence.
- **Phase 4:** Typed capability schemas, action registry, and `SecurityValidator`.
- **Phase 5:** Native WASAPI microphone capture, `faster-whisper` STT, local acoustic wake detector, and `AudioPlayer`.
- **Phase 6:** Live Gemini intelligence (`google-genai` v1.73.1), multilingual Telugu/English dialogue, multi-turn memory, and multi-provider failover.
- **Phase 7:** Secure Real Windows Capabilities:
  - Real Windows application launching (`notepad`, `calculator`, `explorer`, `browser`, etc.) via `shell=False`.
  - Native Windows volume and media control via `winmm.dll` CoreAudio and virtual keys.
  - Safe browser web navigation and URL-encoded search queries.
  - Independent outcome verification and honest non-fabricated reporting.
- **Phase 8 (Completed):** Production Consolidation, Integration & Desktop Readiness:
  - Unified single application entry point (`main.py`) orchestrating all components in one process.
  - 1-click Windows desktop launch script (`launch_miss_minutes.bat`) with windowed mode support.
  - Architecture simplification audit preserving critical security, AI, and UI boundaries.
  - Modernized production dependencies (`requirements.txt`) and automated setup scripts (`install.bat`, `install.sh`).
  - Direct developer access in `jarvis.py` (`python jarvis.py` / `python main.py --jarvis`).
  - Headless self-diagnostics runner (`python main.py --diagnostics`).
  - Phase 8 production integration test suite (146 total passed tests).
- **Phase 9 (Completed):** Security & Production Hardening:
  - Expanded anti-injection filters rejecting script files (`.bat`, `.cmd`, `.ps1`, `.vbs`, `.sh`), path traversal (`../../`), prompt injection overrides, and credential access.
  - Local abuse defense: sliding-window rate limiting (20 requests / 5s), consecutive violation cooldown (5 denials -> 10s cooldown), and rapid app launch throttling (3 launches / 3s).
  - Absolute OFFLINE authority: all 6 active states deterministically cut off to OFFLINE, stopping transient timers, gating all capabilities, and blocking bus dispatch.
  - Agent message bus loop prevention and delegation depth limit (`max_delegation_depth: 3`).
  - Hardened audit logging with automatic regex-based secret redaction (`AIza...`, `sk-...`, `gsk_...`, `ghp_...`, Bearer tokens) and 1 MB rotating JSONL file sink with 2 backup archives.
  - Comprehensive Phase 9 hardening test suite (19 tests, 165 total tests passed).
- **Phase 10 (Completed):** Windows EXE Packaging & Desktop Distribution:
  - Production PyInstaller onedir windowed build (`packaging/MissMinutes.spec` -> `dist/MissMinutes/MissMinutes.exe`).
  - Original multi-resolution clock companion Windows application icon (`packaging/MissMinutes.ico`).
  - Inno Setup 6 installer (`dist/installer/MissMinutes_Setup.exe`, 159 MB with max LZMA2 compression).
  - PowerShell desktop and Start Menu shortcut integration (`packaging/installer/install_desktop.ps1`).
  - Runtime resource and per-user configuration isolation (`~/.miss_minutes/config.env`, `~/.miss_minutes/models`).
  - Headless diagnostics preserved in packaged binary (`MissMinutes.exe --diagnostics`).
  - 100% test pass rate preserved (165/165 tests passed).

---

## 11. Verification & Quality Gates

The entire test suite passes deterministically in offline environments without external API keys:
```bash
python -m pytest tests/ -v
```
All **165 automated tests** across 11 test suites must achieve a 100% pass rate before authorizing subsequent phases.
