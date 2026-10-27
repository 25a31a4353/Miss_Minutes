# Repository Audit: Jarvis Codebase & Runtime Baseline

**Audit Date:** 2026-10-23  
**Auditor:** Senior Software Architect & Windows Desktop Application Engineer  
**Host Environment Confirmed:** Windows 11 Pro 64-bit (`Windows-11-10.0.26300-SP0`, AMD64)  
**Python Runtime Confirmed:** Python 3.14.3 (MSC v.1944 64-bit AMD64)  
**Reference Repository:** `https://github.com/25a31a4353/Jarvis` (Commit `e69c9183c3803a38e0bf47d8ceebd3bbb0ddeca9`)  
**Product Specification:** `Miss_Minutes_PRD.md` (Contract Baseline)

---

## 1. Executive Summary

The checked-out repository `Jarvis` is marketed in its documentation as a "voice-controlled AI executive assistant for macOS, Windows, and Linux" featuring automated app launching, YouTube playback, WhatsApp messaging, email briefings, stock market recommendations, and a 3D Iron Man HUD.

Direct inspection and concrete execution tests on Windows 11 reveal:
1. **Broken on Windows:** The core action executor (`jarvis_actions.py`) unconditionally executes macOS-specific CLI tools (`open`, `osascript`) and looks for `/Applications/*.app`. Any attempt to launch an app, open a website, search YouTube, search Google, or adjust volume on Windows immediately raises `FileNotFoundError: [WinError 2] The system cannot find the file specified`.
2. **Missing Dependencies & Setup Gaps:** The Windows installer (`install.bat`) attempts `pip install pyttsx3 pyaudio`, neither of which is present in `requirements.txt`. Furthermore, `install.bat` does not prompt for or configure the Groq API key (unlike `install.sh`), leaving Windows users with a broken setup flow.
3. **Fictitious / Unbacked Features:** The "email briefing" feature in `jarvis_actions.py:get_mail_brief` returns a hardcoded, fabricated string (`"You have 3 unread priority emails: team project sync, server alert, and a weekly client report."`) when no mail cache is present, pretending to have read actual mail.
4. **Disconnected UI:** `jarvis_workplace.html` is an HTML5/Canvas visualization that polls `/api/state` every 400ms. Neither `jarvis_voice.py`, `jarvis_brain.py`, nor `jarvis_actions.py` runs an HTTP or WebSocket server; opening the HTML file in a browser results in permanent 404/network errors and complete disconnection from the Python backend.
5. **No Security Boundary:** The existing architecture has zero permission validation, no typed schema, no allowlist enforcement, and no manual ON/OFF state.
6. **Zero Tests:** The repository contains zero automated test files (`python -m unittest discover` yields `Ran 0 tests in 0.000s`).

---

## 2. Tracked File Tree & Component Responsibilities

| File | Size | Tracked / Status | Stated Purpose | Actual Implemented Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| `INDEX.md` | 6.8 KB | Tracked | Complete setup & feature documentation | Marketing document with inaccurate claims regarding Windows compatibility, free tier quotas, and 100% uptime. |
| `Jarvis_Setup_Guide.html` | 8.6 KB | Tracked | Printable setup guide with Tenglish notes | HTML version of setup instructions; repeats macOS-centric workflow. |
| `Jarvis_Setup_Guide.pdf` | 356 KB | Tracked | Formatted PDF setup guide | Binary export of setup guide. |
| `README.md` | 1.8 KB | Tracked | Quick start guide | Brief summary of commands, HUD, and failover engine. |
| `install.bat` | 1.3 KB | Tracked | Windows 1-click installer | Installs `requirements.txt` + `pyttsx3 pyaudio`, activates venv, then launches `jarvis_voice.py`. Omits API key setup. |
| `install.sh` | 2.4 KB | Tracked | macOS/Linux 1-click installer | Installs requirements, prompts for Groq key and writes to `~/.openjarvis/free.key` with `chmod 600`. |
| `jarvis_actions.py` | 6.3 KB | Tracked | Local system automation | Hardcoded regex routing to macOS commands (`open`, `osascript`) and mock routines. |
| `jarvis_brain.py` | 4.1 KB | Tracked | Hybrid cloud + offline AI engine | Tightly coupled to Groq OpenAI client; contains cooldown fallback logic and in-memory chat history. |
| `jarvis_market.py` | 4.7 KB | Tracked | Stock intelligence & Buy/Sell signals | Scrapes unofficial Yahoo Finance JSON API; computes naive moving averages to issue buy/sell flags. |
| `jarvis_voice.py` | 3.1 KB | Tracked | Continuous microphone & TTS loop | Unbounded loop using `speech_recognition` (Google STT) and `say`/`pyttsx3`. No manual OFF state. |
| `jarvis_workplace.html` | 30.8 KB | Tracked | Holographic Iron Man HUD | Rich HTML5/Canvas/CSS HUD that continuously polls `/api/state`; completely orphaned from Python scripts. |
| `requirements.txt` | 142 B | Tracked | Python dependencies | Lists `openai>=1.12.0`, `SpeechRecognition>=3.10.0`, `requests>=2.31.0`, `certifi>=2024.2.2`, `psutil>=5.9.0`. |
| `Miss_Minutes_PRD.md` | ~12 KB | Added in Phase 0 | Master Product Contract | Product vision, non-goals, security boundary, architecture, roadmap, and acceptance criteria. |

---

## 3. Confirmed Dependencies & Local Environment Findings

### 3.1 Host & Runtime Environment
- **Operating System:** Windows 11 Version 10.0.26300 (AMD64 architecture).
- **Python Version:** Python 3.14.3 (`MSC v.1944 64 bit (AMD64)`).
- **Git State:** Clean on `origin/main` (commit `e69c918`), no branches or pending commits.

### 3.2 Dependency Analysis & Package Health

| Package in `requirements.txt` | Installed on System? | Version Detected | Evaluation & Compatibility |
| :--- | :--- | :--- | :--- |
| `openai` | Yes | 2.30.0 | Groq-compatible client available, but PRD requires Gemini as primary and provider abstraction. |
| `SpeechRecognition` | No | None | Standard library for STT, but requires PyAudio or sounddevice for microphone capture. |
| `requests` | Yes | 2.32.5 | Healthy, current. |
| `certifi` | Yes | 2026.2.25 | Healthy, current. |
| `psutil` | Yes | 7.2.2 | Healthy, current. |

### 3.3 Undeclared & Missing Dependencies
- `pyttsx3`: Called in `jarvis_voice.py:25` and referenced in `install.bat:31`, but missing from `requirements.txt`.
- `pyaudio`: Required by `speech_recognition.Microphone()`; listed in `install.bat:31`, missing from `requirements.txt`. Note: PyAudio builds on Windows with Python 3.14 can be problematic unless pre-compiled wheels or `sounddevice` alternatives are used.
- `google-genai`: Already installed on system (version `1.73.1`), ready for Gemini AIProvider implementation.
- `edge-tts`: Already installed on system (version `7.3.1`), highly suited for clean, non-blocking, multi-lingual (English/Telugu) TTS.
- `PySide6`: Not yet installed. Dry-run package inspection (`pip install --dry-run PySide6`) successfully located `PySide6-6.12.0` with `cp310-abi3-win_amd64.whl`, confirming full binary compatibility with Python 3.14 on Windows 64-bit without compilation issues.

---

## 4. Concrete Module-by-Module Audit

### 4.1 `jarvis_actions.py`
1. **Direct Windows Failure:** Line 40 defines `_open(args)` as `subprocess.run(["open"] + args, capture_output=True)`. Line 44 defines `_osa(script)` as `subprocess.run(["osascript", "-e", script])`. Both `open` and `osascript` exist only on macOS. On Windows:
   - Calling `try_action("google python")` crashes with `FileNotFoundError: [WinError 2] The system cannot find the file specified` at line 144.
   - Calling `try_action("volume up")` crashes with `FileNotFoundError: [WinError 2] The system cannot find the file specified` at line 161.
2. **macOS App Discovery:** Lines 47–60 (`_apps()`) inspects `/Applications`, `/System/Applications`, and `~/Applications` for `*.app` bundles. On Windows, this directory list returns empty dictionary `{}`. Line 63 (`find_app(name)`) fails to locate any Windows `.exe` or Start Menu shortcuts.
3. **Fabricated Mail Briefing:** Line 94 in `get_mail_brief()` falls back to:  
   `"You have 3 unread priority emails: team project sync, server alert, and a weekly client report."`  
   This creates a deceptive illusion of functionality without user authentication, IMAP/OAuth setup, or mail access.
4. **False Action Confirmation:**
   - Line 138: `try_action("play lofi on youtube")` returns `"Playing lofi on YouTube."` even though it only constructs a search URL and runs `open` (which crashes).
   - Line 162: Returns `"Volume increased."` even if `_osa()` fails or is missing.

### 4.2 `jarvis_voice.py`
1. **Unbounded Blocking Loop:** Lines 65–97 run an infinite `while True` loop blocking the thread. There is no cancellation token, event, or flag to pause or stop listening.
2. **False Wake-Word Logic:**
   - Lines 76–78 check `if "jarvis" in q_clean: q_clean = q_clean.replace("jarvis", "").strip(" ,.!?")`.
   - If the user speaks `"what time is it"`, `"jarvis"` is not in `q_clean`. The condition is skipped, leaving `q_clean = "what time is it"`. Line 84 immediately passes this to `jarvis_brain.think()`.
   - **Result:** The assistant responds to *every single conversation or noise* captured in the room without requiring the wake word.
3. **Synchronous & Flawed TTS:**
   - Line 26: `pyttsx3.init()` is invoked inside every call to `speak()`. On Windows SAPI5, repeated initialization and destruction of the COM engine in the same thread causes COM error deadlocks or voice stutter.
   - Line 29: Silently suppresses exceptions with `except Exception: pass`, preventing error diagnosis.
4. **Cloud Privacy Violation:** Line 72 calls `recognizer.recognize_google(audio)`. All room audio is uploaded to Google's public speech endpoint over HTTP/HTTPS without user disclosure, toggle, or privacy policy.

### 4.3 `jarvis_brain.py`
1. **Invalid Model Names:** Line 15 defines `MODELS = ["openai/gpt-oss-20b", "llama-3.3-70b-versatile", "qwen/qwen3.8-27b"]`. The model `"openai/gpt-oss-20b"` is not a valid Groq model identifier and will always generate a 404 or 400 API error before falling back to `llama-3.3-70b-versatile`.
2. **Missing Provider Abstraction:** Hardcoded to `OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")`. Gemini is absent.
3. **Unbounded Memory Growth:** Line 113 appends user and assistant messages to module-level list `_history` without pruning or bounds. Over extended runtime, this causes memory bloat.
4. **Thread-Safety Hazards:** Globals `_client`, `_history`, and `_cooldown_until` are mutated without locking or thread-synchronization primitives.

### 4.4 `jarvis_market.py`
1. **Unofficial API Scraping:** Uses `https://query1.finance.yahoo.com/v8/finance/chart/` with a spoofed Mac Safari User-Agent (line 18). This endpoint has no SLA, is frequently throttled or blocked by Yahoo, and violates commercial scraping policies.
2. **Unregulated Financial Advice:** Generates buy/sell signals (`STRONG BUY`, `BUY / ACCUMULATE`, `STRONG SELL / SHORT`) based on a simplistic 15-minute SMA cross. This violates PRD Non-Goals (Section 3) and must be excluded from the MVP.

### 4.5 `jarvis_workplace.html`
1. **Disconnected Polling Architecture:** Polls `/api/state?lv=` every 400ms (lines 557–572). The Python codebase has no web framework (Flask, FastAPI, Tornado) and serves no endpoints.
2. **Visual Inspiration Only:** The SVG audio oscilloscope, radial gauge, and dark control room aesthetic offer strong visual cues for Miss Minutes' retro-futuristic timeline theme, but must be built as a native PySide6 overlay rather than a detached browser tab.

---

## 5. Security, Secrets, Logging, and Privacy Audit

1. **Secret Storage:**
   - `install.sh` saves the Groq API key in plaintext to `~/.openjarvis/free.key`. While it applies `chmod 600`, storing plaintext API keys in home directories without encryption or OS keychain integration is fragile.
   - `install.bat` does not handle keys at all, leaving Windows users without guidance.
   - `jarvis_brain.py:27` reads `GROQ_API_KEY` from environment variables, which is acceptable if managed safely.
2. **Logging & Privacy:**
   - No structured audit logging exists.
   - All errors and actions are printed directly to `sys.stdout` via `print()`.
   - Audio is transmitted to third-party endpoints without visual notification or explicit user consent.
3. **Unrestricted / Unvalidated Action Flow:**
   - `jarvis_actions.py` accepts freeform strings from regex and feeds them directly to process execution. While the current regex only matches specific verbs, there is no validation of URL schemes, parameter boundaries, or target executables.

---

## 6. Test Suite Status & Verification Outcomes

### 6.1 Automated Tests
- **Search Query:** `test*.py`, `tests/`
- **Result:** No test files exist in the repository.
- **Execution Command:** `python -m unittest discover`
- **Execution Output:**
  ```text
  ----------------------------------------------------------------------
  Ran 0 tests in 0.000s

  NO TESTS RAN
  ```
  *(Exited with code 1)*

### 6.2 Manual Verification Tests Performed

| Test Item | Command / Invocation | Expected Behavior | Actual Observed Outcome | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| Date/Time Action | `python -c "import jarvis_actions; print(jarvis_actions.try_action('what time is it'))"` | Returns formatted current time | `It is currently 07:42 PM` | PASS (Deterministic text only) |
| Windows Volume Control | `python -c "import jarvis_actions; print(jarvis_actions.try_action('volume up'))"` | Adjusts system volume | `FileNotFoundError: [WinError 2] The system cannot find the file specified` (`osascript`) | FAIL |
| Windows Browser Search | `python -c "import jarvis_actions; print(jarvis_actions.try_action('google python'))"` | Opens browser to Google | `FileNotFoundError: [WinError 2] The system cannot find the file specified` (`open`) | FAIL |
| PySide6 Availability | `pip install --dry-run PySide6` | Check wheel availability for Python 3.14 on Win64 | `Would install PySide6-6.12.0 ... (cp310-abi3-win_amd64.whl)` | PASS (Binary compatible wheel available) |

---

## 7. Audit Conclusions & Architecture Mandates

1. **Do not preserve the current process execution logic:** All `subprocess.run(["open", ...])` and `subprocess.run(["osascript", ...])` calls must be discarded.
2. **Introduce Strict Typed Security Gate:** AI output or speech parsing must produce a typed `ActionRequest` that passes an independent allowlist validator before reaching an OS-specific executor.
3. **Replace Uncontrolled Voice Loop:** Build a state-driven service with an explicit manual `OFF` state that stops audio capture and wake detection completely.
4. **Establish Gemini as Default AI Provider:** Use `google-genai` with a clean `AIProvider` protocol, reserving Groq as a fallback option.
5. **Desktop Foundation:** Adopt PySide6 for a native transparent, always-on-top desktop overlay with retro-futuristic Miss Minutes clock styling.
