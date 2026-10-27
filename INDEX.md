# 🚀 JARVIS AI PERSONAL ASSISTANT — Product Requirements & System Architecture

**Document Status:** Authoritative Product Requirements Document (PRD) & Architecture Reference for Jarvis  
**Version:** 2.5 (Dual-Agent Integrated Edition)  
**Target Platform:** Windows 10/11 (64-bit), macOS, Linux  
**Authoritative Implementation:** `jarvis.py` (with `jarvis_brain.py`, `jarvis_voice.py`, `jarvis_actions.py`, `jarvis_market.py`)  
**Dual-Agent Partner:** Miss Minutes (User-Facing Companion)  
**Last Updated:** October 2026  
**License:** Open Source & Free to Use  

---

## 1. Product Vision & Identity

### 1.1 Product Vision
Jarvis is an executive-level, highly capable desktop AI co-pilot designed to provide high-precision technical reasoning, system capability planning, and market analysis. Rather than operating as an isolated, unconstrained script runner, Jarvis serves as the trusted technical engine and strategic counterpart to **Miss Minutes**.

### 1.2 Persona & Identity
- **Gender:** Male.
- **Tone:** Composed, impeccably professional, calm, confident, protective of system security, with a sharp, dry wit.
- **Speech Style:** British cadence ("Certainly, sir", "Right away", "Allow me to review the system parameters"), concise and technically exact.
- **Relationship:** Trusted colleague and lifelong partner to Miss Minutes. He handles technical heavy lifting, system analytics, capability formulation, and security risk assessment.

---

## 2. Critical Architecture Invariant: The Single Jarvis Rule

```text
COUNT(JARVIS_IMPLEMENTATIONS) = 1
```

> [!IMPORTANT]
> **There is exactly ONE Jarvis implementation in this entire system.**
> The authoritative Jarvis codebase consists of:
> - `jarvis.py` (Central agent coordinator implementing the `Agent` protocol)
> - `jarvis_brain.py` (AI reasoning, rate-limit cooldown, and hybrid failover engine)
> - `jarvis_actions.py` (Structured capability planner, URL routing, and app aliasing)
> - `jarvis_voice.py` (Executive voice profile and TTS coordination)
> - `jarvis_market.py` (Live Yahoo Finance analytics and market monitoring)

Any secondary references (such as `agents/jarvis_agent.py`) serve **strictly as integration and compatibility proxies** routing calls to `jarvis.py`. No duplicate brain, persona, or parallel implementation is permitted.

---

## 3. Dual-Agent Collaboration Architecture

Jarvis operates in a collaborative dual-agent model where Miss Minutes acts as the front-of-house desktop companion and Jarvis acts as the technical specialist:

```text
                         USER
                           │
                           ▼
                    ┌──────────────┐
                    │ MISS MINUTES │  ◄── Primary user-facing companion
                    │ (Companion)  │      (Female, warm, witty, playful)
                    └──────┬───────┘
                           │
                     Agent Message  ◄── Typed message bus (AgentMessageBus)
                           │
                           ▼
                    ┌──────────────┐
                    │   JARVIS     │  ◄── Authoritative technical co-pilot
                    │ (jarvis.py)  │      (Male, calm, precise, British wit)
                    └──────┬───────┘
                           │
                  Structured Capability Request
                           │
                           ▼
                  ┌──────────────────┐
                  │ SECURITY         │  ◄── Mandatory security boundary
                  │ VALIDATOR        │      (Default DENY allowlist)
                  └────────┬─────────┘
                           │
                           ▼
                 ALLOWLISTED ACTIONS (Phase 7 Executor)
```

### Delegation Workflow:
1. User expresses an operational or technical intent to Miss Minutes (e.g., *"YouTube open chesi AR Rahman songs play cheyyi"* or *"Check system status"*).
2. Miss Minutes evaluates user rapport and dispatches a structured `AgentMessage` of type `DELEGATION` to Jarvis across the `AgentMessageBus`.
3. Jarvis evaluates parameters, consults `jarvis_actions` and `jarvis_market`, and formulates a typed `CapabilityRequest`.
4. The request must pass `SecurityValidator` before any execution occurs.
5. Jarvis returns an `AgentMessage` of type `RESULT` to Miss Minutes, who synthesizes the final warm confirmation for the user.

---

## 4. AI Provider & Intelligence Architecture

Jarvis utilizes the unified `AIProvider` abstraction with a resilient three-tier failover hierarchy:

```text
AIProvider (ResilientAIProvider)
  ├── 1. Primary: Google Gemini (Official google-genai SDK, gemini-2.5-flash)
  ├── 2. Secondary: Groq Fallback (High-speed cloud inference, llama-3.3-70b-versatile)
  └── 3. Tertiary: MockAIProvider / Local Deterministic Engine (Offline & Test Safe)
```

### 4.1 Multilingual Understanding
Jarvis understands user requests in:
- **English:** *"Check market report for Reliance and Nvidia."*
- **Telugu:** *"Stock market samacharam ela undi?"*
- **Telugu-English Mixed Speech:** *"YouTube lo songs play cheyyadaniki ready cheyyi."*

Transcripts are processed verbatim without early forced translation into English, preserving cultural context and technical nomenclature (Python, API, Gemini, Docker, Nifty).

### 4.2 Bounded Conversation Memory
- History is maintained in thread-safe, memory-bounded ring buffers (`SharedBoundedContext`, default 10 turns).
- Multi-turn follow-up inquiries (e.g., *"What is quantum entanglement?"* → *"Give me a simple example."*) retain prior context without unbounded prompt expansion.
- Sensitive secrets, credentials, and API keys are automatically redacted via regex patterns.

---

## 5. Security Model & Execution Boundaries

> [!CAUTION]
> **Jarvis is an intelligence and capability formulation engine, NOT an arbitrary code executor.**

### 5.1 Absolute Prohibitions
Jarvis is strictly forbidden from executing or proposing:
- Arbitrary command-line scripts (`cmd.exe`, `powershell.exe`, `pwsh`, `bash`, `sh`).
- Arbitrary Python code execution (`exec()`, `eval()`, `os.system()`).
- File deletion, bulk filesystem overwriting, or directory purging.
- Registry modifications (`reg.exe`, `regedit.exe`).
- Disabling antivirus, Windows Defender, or firewall settings.
- Privilege elevation (`runas`, sudo).
- Accessing credential stores, password vaults, or browser session tokens.

### 5.2 Mandatory Security Pipeline
Every operational request follows this immutable sequence:
```text
Utterance → faster-whisper STT → Gemini/AI → Structured Intent → CapabilityRequest → SecurityValidator (ALLOW / DENY / CONFIRM) → Typed Executor → Verified Result → TTS
```

### 5.3 Authoritative Master OFFLINE Gate
When the assistant is placed in the **OFFLINE** state:
- All microphone recording, wake-word detection, and audio playback immediately halt.
- `jarvis_brain.think()` and `jarvis_actions.try_action()` refuse all execution and return an explicit offline security notice.
- No network requests to Gemini or Groq are dispatched.

---

## 6. Voice & Hardware Interaction (Phase 5 Foundation)

Jarvis shares the unified Phase 5 Voice Architecture with Miss Minutes:
- **Microphone Capture:** Windows-compatible WASAPI capture via `QMediaDevices` and `MicrophoneDevice` with silence detection and timeout guards.
- **Wake Word:** Local acoustic detector for *"Hey Minutes"* (strictly non-authenticating).
- **Speech-to-Text:** Local `faster-whisper` (int8 tiny model) supporting English, Telugu, and code-switching verbatim.
- **Text-to-Speech:** Shared `VoiceService` with distinct voice profiles:
  - **Miss Minutes:** Warm Southern cadence (`en-US-JennyNeural`, `te-IN-ShrutiNeural`).
  - **Jarvis:** Executive British cadence (`en-GB-RyanNeural`, `te-IN-MohanNeural`).
- **Speaker Playback:** Asynchronous `AudioPlayer` via `QMediaPlayer` / `QAudioOutput` with temporary file auto-purging.

---

## 7. Voice Commands & Capabilities Matrix

| Command Category | Example Utterance | Current Implementation Status | Handling Path |
| :--- | :--- | :---: | :--- |
| **System Diagnostics** | *"Jarvis, check system status"* | ✅ **Implemented** | `jarvis.py` → `GET_SYSTEM_STATUS` → CPU/RAM/Battery meters |
| **Web Navigation** | *"Jarvis, open YouTube"* | ✅ **Implemented & Verified** | `jarvis_actions.py` → `OPEN_WEBSITE` → Allowlisted URL |
| **Media Search** | *"Play AR Rahman songs on YouTube"* | ✅ **Implemented & Verified** | `jarvis_actions.py` → `PLAY_YOUTUBE` → Encoded search query |
| **Time & Date** | *"What time is it, Jarvis?"* | ✅ **Implemented** | `jarvis.py` → `GET_TIME` → Local system clock |
| **Market Analysis** | *"Stock market report"* / *"Nifty analysis"* | ✅ **Implemented** | `jarvis_market.py` → Yahoo Finance live quote analysis |
| **Volume Control** | *"Volume up"* / *"Mute"* / *"Set volume to 50"* | ✅ **Implemented & Verified** | `actions/windows_executor.py` → Native `winmm.dll` CoreAudio & Virtual Keys |
| **Real App Execution** | *"Launch Notepad on Windows"* | ✅ **Implemented & Verified** | `actions/windows_executor.py` → Verified allowlisted process launcher (`shell=False`) |
| **Media Playback Control** | *"Pause music"* / *"Next track"* | ✅ **Implemented & Verified** | `actions/windows_executor.py` → Windows virtual media key events |
| **WhatsApp Automation** | *"Send WhatsApp message to Pallavi"* | ⏳ **Future** | WhatsApp Web automation requiring explicit UI confirmation |
| **Email Briefing** | *"Read unread emails"* | ⏳ **Future** | OAuth-scoped mail summary requiring explicit user consent |

---

## 8. Implementation Roadmap & Current Status

### ✅ Completed & Active (Phases 0–8)
- **Phase 0:** Repository audit, architectural baseline, and migration plan.
- **Phase 1:** Safe desktop shell, PySide6 foundation, and master OFFLINE switch.
- **Phase 2:** Visual state machine, expressions, position persistence, and reduced-motion mode.
- **Phase 3:** Dual-agent message bus, agent protocol, and shared bounded context.
- **Phase 4:** Capability architecture, typed schemas, and `SecurityValidator`.
- **Strict Architecture Correction:** Verification that `COUNT(JARVIS_IMPLEMENTATIONS) = 1`.
- **Phase 5:** Real voice layer (microphone capture, `faster-whisper` STT, local wake detector, audio player).
- **Phase 6:** Live Gemini intelligence (`google-genai` v1.73.1, multilingual Telugu/English dialogue, multi-turn memory).
- **Phase 7:** Secure Real Windows Capabilities:
  - Real Windows application launcher using verified binary allowlist (`notepad`, `calculator`, `explorer`, `browser`, etc.).
  - Native Windows master volume and media controls via `winmm.dll` CoreAudio and virtual key events.
  - Browser navigation for allowlisted web targets and URL-encoded search queries.
  - Independent execution outcome verification and honest non-fabricated reporting.
- **Phase 8 (Completed):** Production Consolidation, Integration & Desktop Readiness:
  - Unified single application entry point (`main.py`) orchestrating all components in one process.
  - 1-click Windows desktop launch script (`launch_miss_minutes.bat`) with `pythonw` windowed mode.
  - Architecture simplification audit preserving critical security and UI boundaries.
  - Modernized `requirements.txt` and automated installation scripts (`install.bat`, `install.sh`).
  - Direct developer access in `jarvis.py` (`python jarvis.py` / `python main.py --jarvis`).
  - Headless self-diagnostics runner (`python main.py --diagnostics`).
  - Phase 8 production integration test suite (145 total passed tests).

### 🔮 Future Roadmap (Phases 9–10)
- **Phase 9:** Security Hardening & Production Hardening (fine-grained audit alerts, rate throttling, configuration sandboxing).
- **Phase 10:** Standalone Windows EXE Packaging & Installer (`pyinstaller` single-binary bundle, setup wizard, desktop icon).

---

## 9. Launching Miss Minutes & Jarvis

### Production Desktop Launch (Packaged Application)
- **Installer:** Run `dist\installer\MissMinutes_Setup.exe` to install to `%LOCALAPPDATA%\Programs\MissMinutes` with Start Menu and Desktop shortcuts.
- **Double-click Desktop Shortcut:** `Miss Minutes` on the desktop.
- **Direct Executable:** `dist\MissMinutes\MissMinutes.exe` (windowed native executable; no terminal, no Python installation required).

### Developer Launch
- **Launcher Script:** Double-click `launch_miss_minutes.bat`.
- **Command-Line:**
```bash
python main.py                # Standard desktop launch (IDLE / saved state)
python main.py --offline      # Start forced into OFFLINE state
python main.py --diagnostics  # Run automated headless self-test suite
python main.py --jarvis       # Direct developer access to Jarvis co-pilot
python main.py --version      # Print system version info
```

---

## 10. Holographic Iron Man HUD Dashboard

For visual monitoring and cyber-aesthetic reference, double-click `jarvis_workplace.html` in any modern browser:
- **Central Reactor Core:** Pulsing Iron Man arc reactor heart with quantum orbital nodes.
- **Audio Oscilloscope:** 4-layer neon waveform responding dynamically to voice input.
- **Live Market Tickers:** Real-time stock quotes with Buy/Sell algorithmic indicators.
- **Neural Pipeline:** Visual representation of speech processing: `MIC → EAR → MIND → HANDS → VOICE`.
- **System Vitals:** Live meters for CPU, RAM, Disk, and Battery.

---

## 11. Verification & Quality Gates

The complete test suite runs deterministically without network or API keys:
```bash
python -m pytest tests/ -v
```
All **165 unit, lifecycle, security, voice, Gemini provider, capability, production integration, and Phase 9 hardening tests** must pass with 100% compliance before any deployment.
