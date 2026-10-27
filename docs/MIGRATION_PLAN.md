# Miss Minutes: Migration & Refactoring Plan

**Target Application:** Miss Minutes Native Windows Desktop Assistant  
**Source Codebase:** Jarvis v2.0 (Branch `main`, Commit `e69c918`)  
**Guiding Principle:** Safe transition without loss of Git history; strict preservation of original files until replacements are tested and accepted.

---

## 1. Module Disposition Matrix

Each file in the existing repository is categorized into one of five disposition states:
- **Reuse:** Retain logic or components with minimal changes.
- **Refactor:** Restructure behind new interfaces, types, and security controls.
- **Replace:** Completely rewrite using Windows-native APIs and modern patterns.
- **Defer:** Move out of MVP scope for future phase evaluation.
- **Archive / Deprecate:** Retain for historical reference; do not load at runtime.

| Existing File | Disposition | Rationale & Migration Strategy |
| :--- | :--- | :--- |
| `jarvis_brain.py` | **Refactor** | Reuse rate-limit detection regex (`_retry_after_seconds`), exponential cooldown logic, and concise system prompt style. Refactor into `ai/provider.py`, `ai/gemini_provider.py`, and `ai/groq_provider.py`. Remove hardcoded `openai/gpt-oss-20b`. |
| `jarvis_actions.py` | **Replace** | The entire module relies on macOS `open`, `osascript`, and `/Applications/*.app`. Discard macOS subprocesses. Replace with `intents/` schema, `security/validator.py`, and `actions/windows_executor.py`. Retain known website aliases and search URL patterns. |
| `jarvis_voice.py` | **Replace** | Unbounded blocking `while True` loop and flawed substring wake-word filter must be replaced with an asynchronous, multi-threaded voice service in `voice/lifecycle.py` that implements a genuine `OFF` state and `PySide6` signal integration. |
| `jarvis_market.py` | **Defer** | Stock recommendations, buy/sell calls, and scraping Yahoo Finance are explicitly excluded from the MVP by PRD Section 3. Preserve file intact for potential post-MVP plugin, but isolate from main app import path. |
| `jarvis_workplace.html` | **Reference / Inspect** | Visual inspiration for animations, radial timeline designs, and color palettes. The actual app shell will be native PySide6. The HTML HUD will not be loaded or served in MVP. |
| `requirements.txt` | **Refactor** | Pin verified Windows-compatible versions (`PySide6`, `google-genai`, `edge-tts`, `pydantic`, `psutil`). Separate dev/test dependencies (`pytest`, `pytest-qt`). |
| `install.bat` | **Refactor** | Rewrite to set up a clean Python venv, verify Python 3.11–3.14 on Windows, install tested wheels, generate `.env.example`, and launch the desktop app cleanly. |
| `install.sh` | **Archive** | Retain for macOS/Linux reference; Miss Minutes targets Windows 10/11 native. |
| `Jarvis_Setup_Guide.html/pdf` | **Archive** | Retain as reference artifacts; create fresh Miss Minutes Windows user guide in `docs/SETUP_GUIDE.md` during release packaging. |
| `INDEX.md` / `README.md` | **Refactor** | Update repository documentation to reflect Miss Minutes vision, true Windows capabilities, and accurate system requirements. |

---

## 2. Working Behaviors to Preserve vs. Behaviors to Reject

### 2.1 Behaviors Worth Preserving
1. **Adaptive Rate-Limit Cooldown Engine:**
   - In `jarvis_brain.py:50-64`, parsing `Retry-After` headers and string patterns like `"try again in Xm Ys"` prevents tight-loop hammering of APIs. This will be integrated into the `AIProvider` base class.
2. **Concise Spoken Prompting:**
   - In `jarvis_brain.py:21-23`, the system prompt instructs the assistant to respond in 1–2 crisp sentences without corporate filler. This aligns with Miss Minutes' cheerful, snappy timeline guide personality.
3. **Common Web & App Aliases:**
   - In `jarvis_actions.py:14-36`, aliases like `"vs code" -> "Visual Studio Code"`, `"chrome" -> "Google Chrome"` provide good baseline mappings. These will be ported to the Windows application allowlist registry.
4. **Local Date & Time Handling:**
   - In `jarvis_actions.py:171-175`, clean deterministic local time/date formatting provides instant feedback without cloud latency.

### 2.2 Behaviors to Reject & Prohibit
1. **Fake Feature Responses:**
   - Reject `jarvis_actions.py:get_mail_brief` returning mock emails. Unimplemented features must be honestly reported as unavailable.
2. **False Action Success Claims:**
   - Reject claiming an action succeeded before the executor has verified execution.
3. **Arbitrary Process / Script Execution:**
   - Reject passing raw strings into system shells.
4. **Always-Listening Uncontrolled Mic Loop:**
   - Reject continuous un-gated microphone loops that lack an explicit manual OFF switch.
5. **Unofficial Financial Advice:**
   - Reject uncertified buy/sell stock signals.

---

## 3. Windows-Specific Rewrite Needs

| Feature Area | Legacy Jarvis Implementation | Required Miss Minutes Windows Implementation |
| :--- | :--- | :--- |
| **URL & Browser Launching** | `subprocess.run(["open", url])` | `webbrowser.open(url)` or `os.startfile(url)` using default Windows browser. |
| **Application Launching** | `subprocess.run(["open", "-a", app])` searching `/Applications` | Safe allowlisted launch using verified paths: `C:\Program Files\...`, Start Menu shortcuts (`.lnk`), or Windows App Execution Aliases. |
| **System Volume Control** | `osascript -e "set volume ..."` | Windows CoreAudio API via `pycaw` or safe `win32api` key events (`VK_VOLUME_UP`, `VK_VOLUME_DOWN`, `VK_VOLUME_MUTE`). |
| **Text-to-Speech (TTS)** | `subprocess.run(["say", ...])` / `pyttsx3` inside loop | Non-blocking async TTS using `edge-tts` (supports high quality neural voices, English and Telugu) or persistent Windows SAPI5 worker thread. |
| **Microphone & Wake Word** | `speech_recognition.Microphone()` + Google HTTP API | Threaded audio capture via PyAudio/sounddevice with local wake detector ("Hey Minutes") and explicit mute/unmute control. |
| **Desktop UI / Overlay** | Browser tab opening `jarvis_workplace.html` | Native `PySide6` window with `Qt.WindowStaysOnTopHint`, `Qt.FramelessWindowHint`, and `Qt.WA_TranslucentBackground`. |

---

## 4. Preservation of Original Code & Git Recovery

To maintain full transparency, auditability, and zero risk of code loss:
1. **No Destructive Operations:** Original files (`jarvis_brain.py`, `jarvis_voice.py`, `jarvis_actions.py`, `jarvis_market.py`, `jarvis_workplace.html`) will remain intact in the repository root or be organized into a dedicated `legacy/` directory only after Phase 1 foundation is operational.
2. **Modular Target Structure:** All new Miss Minutes code will reside in structured subpackages (`app/`, `ui/`, `voice/`, `ai/`, `intents/`, `security/`, `actions/`, `config/`, `tests/`).
3. **Git Recovery Points:** Any future refactoring will proceed in discrete, reviewable commits. Git branches can be tagged (`legacy-jarvis-baseline`) to ensure instantaneous rollback at any moment.
4. **Parallel Test Verification:** During development, legacy functions and new Windows executors will be compared side-by-side in tests to verify regressions.

---

## 5. Migration Risk Assessment & Mitigation

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Python 3.14 Compatibility** | Some compiled C-extension packages might lack pre-built wheels for Python 3.14. | Verified that `PySide6` provides `cp310-abi3` universal wheels that install cleanly on 3.14. For audio, prioritize pure-python/CFFI packages or provide fallback push-to-talk test modes. |
| **Microphone Permissions on Windows** | Windows 10/11 microphone privacy settings may block app access. | Implement proactive mic device availability check at startup; display clear instructional guidance in the UI if access is denied. |
| **High CPU Usage in Overlay** | Continuous animated rendering could cause CPU spikes on laptops. | Utilize Qt hardware acceleration, event-driven repainting, and reduced framerate during `IDLE` / `OFFLINE` states. Respect system reduced-motion preferences. |
| **Multi-lingual STT/TTS Challenges** | Telugu and mixed Telugu-English voice recognition accuracy varies across providers. | Document supported language capabilities transparently; provide text input fallback and allow voice model selection. |
