# Miss Minutes: Implementation Roadmap & Phase Deliverables

**Roadmap Version:** 1.0 (Phase 0 Baseline)  
**Execution Model:** Incremental, Test-Driven Vertical Slices  
**Target Milestone:** Native Windows 10/11 Miss Minutes Desktop AI Assistant

---

## 1. Overview of Phases

In strict alignment with `Miss_Minutes_PRD.md` Section 12, implementation is organized into sequential, isolated phases. Each phase has explicit dependencies, concrete deliverables, and measurable acceptance criteria that must be verified before proceeding to the next.

| Phase | Title | Focus Area | Deliverable Artifacts |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Discovery & Planning** | Baseline audit, architecture, security model, and migration strategy | `docs/` specifications, PRD baseline |
| **Phase 1** | **Safe Desktop Foundation** | App entry point, PySide6 shell, settings, logging, test harness | `app/main.py`, `ui/window.py`, initial tests |
| **Phase 2** | **Character UI & State Machine** | Transparent floating overlay, clock face, state animations | `ui/character.py`, `ui/state_machine.py` |
| **Phase 3** | **Voice Lifecycle** | Device selection, mic start/stop, push-to-talk, STT/TTS | `voice/audio_capture.py`, `voice/tts.py` |
| **Phase 4** | **Wake Phrase** | "Hey Minutes" wake-word detection, offline mute handling | `voice/wake.py`, wake benchmarks |
| **Phase 5** | **AI Providers & Conversation** | Gemini primary, Groq fallback, typed intent extractor | `ai/provider.py`, `ai/gemini.py`, `ai/groq.py` |
| **Phase 6** | **Security & Safe Actions** | Typed ActionRequest, allowlist validator, Windows executors | `security/validator.py`, `actions/windows.py` |
| **Phase 7** | **Integrated Assistant** | End-to-end pipeline: Wake → STT → AI → Gate → Exec → TTS | Integrated desktop app, smoke tests |
| **Phase 8** | **Packaging & Release Readiness** | PyInstaller `.exe` build, clean install verification, release docs | Standalone `.exe`, user documentation |

---

## 2. Recommended First Vertical Slice (Phase 1 Detail)

### 2.1 Why Phase 1 is the Safest Starting Point
Attempting to connect microphones, Gemini API calls, speech recognition, and OS actions simultaneously in a single leap creates an untestable, brittle system with multiple failure points.

The recommended first slice is:
> **A native PySide6 window/overlay, a tested manual ON/OFF lifecycle, a clear UI state machine and unit/UI tests, with no microphone, AI, or operating system actions yet.**

### 2.2 Rationale
1. **Validates the GUI Stack on Windows 11 & Python 3.14:** Confirms that PySide6 window transparency, frameless windowing, and `Qt.WindowStaysOnTopHint` work reliably on the host without graphics driver glitches.
2. **Establishes the Primary Safety Invariant:** Proves the manual `OFF` state is authoritative and that UI state transitions are strictly governed before any audio hardware or AI endpoints are attached.
3. **Establishes the Testing Infrastructure:** Installs `pytest` and `pytest-qt`, proving that automated tests run, pass, and guard against regressions right from day one.
4. **Zero External Dependencies / Zero Cost:** Requires no API keys, no network calls, and no audio permissions.

---

## 3. Detailed Phase Breakdown & Acceptance Criteria

### Phase 0: Discovery & Planning (Current Phase - Completed)
- **Deliverables:**
  - `Miss_Minutes_PRD.md` preserved in repository.
  - `docs/REPOSITORY_AUDIT.md`: Baseline audit of files, dependencies, Windows bugs, and tests.
  - `docs/ARCHITECTURE.md`: Component architecture, data flows, thread separation, and FSM.
  - `docs/MIGRATION_PLAN.md`: Module disposition matrix and legacy preservation plan.
  - `docs/SECURITY_MODEL.md`: Deny-by-default rules, typed schemas, and negative test cases.
  - `docs/IMPLEMENTATION_PHASES.md`: This implementation roadmap.
- **Acceptance Criteria:**
  - Full tracked file tree inspected.
  - Concrete Windows failure points verified with exact error outputs.
  - No code refactoring or external feature implementation performed prior to user approval.

---

### Phase 1: Safe Desktop Foundation
- **Deliverables:**
  - Application entry point: `app/main.py`.
  - Minimal PySide6 application shell and main window controller.
  - Manual ON/OFF switch with explicit visual status (`OFFLINE` vs `IDLE`).
  - Configuration manager: `config/settings.py` (reads `.env`, defaults to safe values).
  - Logging infrastructure: `logging/audit.py` writing structured local JSONL logs.
  - Test harness: `tests/test_lifecycle.py` verifying state transitions.
- **Acceptance Criteria:**
  - Application launches cleanly as a native Windows window.
  - Toggling OFF explicitly enters `OFFLINE` state; toggling ON enters `IDLE`.
  - Closing the application cleanly shuts down Qt event loop without lingering processes.
  - 100% of Phase 1 unit and UI tests pass.

---

### Phase 2: Character UI and State Machine
- **Deliverables:**
  - Floating transparent overlay with retro-futuristic Miss Minutes clock styling.
  - Custom `QPainter` or vectorized graphics rendering (warm amber/gold accents, dark/cream palette).
  - Explicit UI state representations for all 12 FSM states (`OFFLINE`, `IDLE`, `WAKE_DETECTED`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `VALIDATING`, `WORKING`, `SPEAKING`, `SUCCESS`, `ERROR`, `BLOCKED`).
  - Window drag handling, position persistence, and screen boundary snapping.
  - Accessibility: respect Windows reduced-motion preferences.
- **Acceptance Criteria:**
  - Transparent overlay floats above other windows without stealing focus or blocking background clicks outside its bounding shape.
  - UI state updates visibly in response to test triggers.
  - CPU usage remains < 3% during idle state.

---

### Phase 3: Voice Lifecycle & Audio Subsystem
- **Deliverables:**
  - Audio device enumerator and selector: `voice/device.py`.
  - Threaded microphone capture: `voice/capture.py` (WASAPI / PortAudio).
  - Non-blocking TTS engine: `voice/tts.py` (supporting `edge-tts` with high-quality English and Telugu voices, and Windows SAPI5 fallback).
  - Push-to-Talk (PTT) manual trigger mode for debugging without wake words.
- **Acceptance Criteria:**
  - When assistant is `OFF`, audio capture hardware is released; zero bytes read.
  - TTS plays asynchronously without blocking the UI thread or freezing animations.
  - Device disconnects or mic errors are handled gracefully without application crash.

---

### Phase 4: Wake Phrase Engine ("Hey Minutes")
- **Deliverables:**
  - Wake phrase engine behind `WakeDetector` interface: `voice/wake.py`.
  - Evaluation of local/offline wake engines (openWakeWord, Porcupine, or Vosk).
  - Clear manual test mode / simulated wake trigger in UI for controlled testing.
- **Acceptance Criteria:**
  - Assistant transitions from `IDLE` to `WAKE_DETECTED` within 500ms of "Hey Minutes".
  - Assistant does not react to background speech that lacks the wake phrase.
  - When in `OFFLINE` state, wake detection is completely disabled.

---

### Phase 5: AI Providers & Conversational Intelligence
- **Deliverables:**
  - `AIProvider` abstract protocol: `ai/provider.py`.
  - `GeminiProvider`: `ai/gemini_provider.py` using official `google-genai` SDK.
  - `GroqProvider`: `ai/groq_provider.py` fallback adapter.
  - Rate-limit tracker and exponential cooldown engine.
  - System prompt configuring Miss Minutes' helpful, witty timeline persona.
  - Structured intent extractor converting LLM outputs into typed dictionaries.
- **Acceptance Criteria:**
  - Clean startup without any API key; displays graceful missing-credential state in UI.
  - Gemini responses return within 1.5 seconds under normal network conditions.
  - In the event of HTTP 429 on primary provider, cleanly switches to fallback if configured.
  - Conversation history is bounded (max 10 turns) to prevent memory leaks.

---

### Phase 6: Security Validator & Windows-Safe Action Executors
- **Deliverables:**
  - Pydantic schema: `intents/schema.py` (`ActionRequest`, `ActionResult`).
  - Independent validator: `security/validator.py` enforcing deny-by-default allowlists.
  - Confirmation modal UI: `ui/confirmation_dialog.py`.
  - Windows-safe action executors: `actions/windows_executor.py` for:
    - Local Date and Time
    - Google Search (safe URL encoding)
    - YouTube Search (safe URL encoding)
    - Allowlisted Windows Application Launching
    - System Volume Controls (bounded CoreAudio API)
- **Acceptance Criteria:**
  - All negative security test cases (`SEC-001` through `SEC-008`) pass.
  - Malformed or injection payloads fail closed with `BLOCKED` status.
  - Executor reports real outcome; UI never claims success on failure.

---

### Phase 7: Secure Real Windows Capabilities (Completed)
- **Deliverables:**
  - Real Windows capability executor (`actions/windows_executor.py`) with process, URL, web search, YouTube, and volume controls.
  - Curated desktop application allowlist and safe URL validation (`actions/apps.py`).
  - Enhanced SecurityValidator with strict parameter boundary checks (`security/validator.py`).
  - Local audit logging of all security decisions to `~/.miss_minutes/logs/audit.jsonl` and in-memory trace.
  - Comprehensive Phase 7 test suite (`tests/test_phase7_capabilities.py`).
- **Acceptance Criteria:**
  - Approved applications launch with process verification (`shell=False`).
  - Safe browser URLs and Google searches dispatch with URL encoding.
  - YouTube search dispatches safely with honest verification (no false playback confirmation).
  - Native volume adjust and mute controls operate via `winmm.dll` and virtual keys with readback verification.
  - 100% of Phase 7 tests pass (128 total tests in repository).

---

### Phase 8: Production Consolidation, Integration & Desktop Readiness (Completed)
- **Deliverables:**
  - Unified root application entry point (`main.py`) coordinating Miss Minutes UI, Jarvis, Voice, Security, and Capabilities.
  - 1-click Windows desktop launcher (`launch_miss_minutes.bat`) with `pythonw` windowed mode.
  - Architecture simplification audit preserving security boundaries, testability, and single Jarvis invariant (`COUNT(JARVIS_IMPLEMENTATIONS) = 1`).
  - Modernized `requirements.txt` and automated setup scripts (`install.bat`, `install.sh`).
  - Direct developer access in `jarvis.py` (`python jarvis.py` / `python main.py --jarvis`).
  - Headless self-diagnostics runner (`python main.py --diagnostics`).
  - Phase 8 production integration test suite (`tests/test_phase8_production.py`).
- **Acceptance Criteria:**
  - Application launches from a single entry point without requiring multiple terminal windows.
  - Desktop 1-click launcher starts Miss Minutes in windowed mode.
  - Strict invariant preserved: exactly one Jarvis implementation exists.
  - Master OFFLINE switch maintains absolute authority across all consolidated modules.
  - 100% of test suite passes (145 total passed tests).

---

### Phase 9: Security & Production Hardening (Completed)
- **Deliverables:**
  - Expanded anti-injection engine (`security/validator.py`) rejecting shell operators (`&`, `|`, `;`, `` ` ``, `$`, `<`, `>`), script file execution (`.bat`, `.cmd`, `.ps1`, `.vbs`, `.sh`), path traversal (`../../`), credential stores (`cmdkey`, `id_rsa`), and prompt injection override keywords.
  - Local abuse defense with multi-tiered rate limiting: sliding-window capability throttling (max 20 requests / 5s), consecutive denial cooldown (5 denials -> 10s lockout), and rapid app launch throttling (max 3 launches of same app / 3s).
  - Absolute OFFLINE master authority: clean deterministic cutoff from all 6 active assistant states to OFFLINE, cancelling transient QTimers, strictly denying capability validation, and dropping agent message dispatch.
  - Agent message bus loop prevention and delegation depth limit (`max_delegation_depth: 3` in `agents/bus.py`).
  - Hardened audit logging (`security/audit.py`) with automatic credential redaction (Google AIza, OpenAI sk-, Groq gsk_, GitHub ghp_, Bearer tokens) and local rotating JSONL file sink (1 MB limit, 2 backup archives).
  - Dedicated Phase 9 security hardening test suite (`tests/test_phase9_hardening.py`).
- **Acceptance Criteria:**
  - All injection attacks, path traversal, script files, and prompt overrides are strictly denied.
  - Excessive request bursts and repeated security denials trigger rate limits and active cooldowns.
  - Turning the assistant OFF stops all timers and shuts down all capabilities immediately.
  - Agent delegation depth and conversation turns are strictly bounded.
  - Audit logs automatically redact API keys and rotate cleanly upon size threshold.
  - 100% of test suite passes (165 total passed tests).

---

### Phase 10: Final Windows EXE Packaging & Installer (Completed)
- **Deliverables:**
  - Production PyInstaller build specification (`packaging/MissMinutes.spec`).
  - Standalone onedir windowed executable (`dist/MissMinutes/MissMinutes.exe`).
  - Original multi-resolution clock companion icon (`packaging/MissMinutes.ico`).
  - Native Inno Setup 6 installer (`dist/installer/MissMinutes_Setup.exe`).
  - PowerShell desktop and Start Menu shortcut creator (`packaging/installer/install_desktop.ps1`).
  - Headless diagnostics executable support (`MissMinutes.exe --diagnostics`).
  - Runtime resource and per-user configuration isolation (`~/.miss_minutes/config.env`, `~/.miss_minutes/models`).
- **Acceptance Criteria:**
  - Standalone executable runs on Windows 10/11 without requiring Python, Node.js, Git, or terminal invocation.
  - Zero API keys embedded into binary; configuration loaded from user profile or environment variables.
  - Inno Setup installer creates Start Menu and Desktop shortcuts and clean uninstaller.
  - Master OFFLINE switch and SecurityValidator default-deny posture verified in packaged executable.
  - Single Jarvis invariant strictly preserved: `COUNT(JARVIS_IMPLEMENTATIONS) = 1`.
  - 100% test pass rate preserved (165/165 tests passed).
