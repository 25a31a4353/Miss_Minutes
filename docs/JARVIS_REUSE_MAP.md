# Jarvis Reuse & Adaptation Matrix

**Document Purpose:** Detailed technical mapping of existing Jarvis components for the Miss Minutes dual-agent architecture.  
**Guiding Principle:** REUSE → ADAPT → WRAP → SECURE without destroying legacy assets or rebuilding Jarvis from scratch.

---

## 1. Executive Summary

The checked-out repository contains the original Jarvis v2.0 codebase. Rather than replacing Jarvis with an artificial replica, we retain the original modules as reference assets and wrap their valuable concepts behind an adapted `JarvisAgent` abstraction. Unsafe, macOS-specific, and unvalidated logic is isolated and secured.

---

## 2. Component-by-Component Reuse Matrix

| Legacy File | Component / Function | Can Reuse Unchanged? | Can Reuse with Adaptation? | Wrap Behind Adapter? | Must Remain Legacy-Only? | Rationale & Safety Boundary |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `jarvis_brain.py` | `SYSTEM_PROMPT` | No | **Yes** | **Yes** | No | The concise, calm, capable persona prompt is adapted into Jarvis's personality definition in `agents/personalities.py`. |
| `jarvis_brain.py` | `_is_rate_limited` & `_retry_after_seconds` | **Yes** | **Yes** | **Yes** | No | Cooldown math and HTTP 429 parsing regex are preserved in the provider adapter. |
| `jarvis_brain.py` | `_history` | No | **Yes** | **Yes** | No | Module-level unbounded list is replaced with `SharedBoundedContext` (max 10 turns, memory-bounded, thread-safe). |
| `jarvis_brain.py` | `MODELS` list | No | **Yes** | **Yes** | No | Fix invalid `"openai/gpt-oss-20b"` identifier to official Groq model IDs (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`). |
| `jarvis_actions.py` | `SITES` dictionary | **Yes** | **Yes** | **Yes** | No | Pre-approved web aliases (Google, YouTube, WhatsApp, Maps, Drive, GitHub) are reused in Jarvis's knowledge base. |
| `jarvis_actions.py` | `ALIASES` dictionary | **Yes** | **Yes** | **Yes** | No | Application aliases ("vs code", "chrome", "spotify") are preserved for Windows application mapping. |
| `jarvis_actions.py` | `try_action` intent regex | No | **Yes** | **Yes** | No | Intent patterns (search web, YouTube query, date/time) are adapted to produce structured `ActionProposal` objects instead of executing OS commands. |
| `jarvis_actions.py` | `_open` & `_osa` (`subprocess.run`) | **No** | No | No | **Yes (Legacy-only)** | Direct macOS commands (`open`, `osascript`) fail on Windows with `WinError 2`. Banned from execution; replaced by the future security validator & Windows executor. |
| `jarvis_actions.py` | `_apps` (`/Applications/*.app`) | **No** | No | No | **Yes (Legacy-only)** | macOS directory layout does not exist on Windows. Replaced by Windows Start Menu and Registry discovery. |
| `jarvis_actions.py` | `get_mail_brief` | **No** | No | No | **Yes (Legacy-only)** | Hardcoded mock mail response is rejected to maintain strict truthfulness. |
| `jarvis_voice.py` | `speak` & `listen_loop` | No | No | No | **Yes (Legacy-only)** | Unbounded blocking single-thread loop and flawed wake-word substring filter must remain legacy-only. |
| `jarvis_market.py` | `DEFAULT_TICKERS` & analysis | No | **Yes** | **Yes** | No | Watchlist symbols and momentum math are preserved as an optional domain query tool for Jarvis, with financial advice disclaimers. |
| `jarvis_workplace.html` | Visual styling & HUD | No | No | No | **Yes (Legacy-only)** | HUD graphics provide reference inspiration for theme tokens; not executed in native PySide6 runtime. |

---

## 3. Preservation Strategy

1. **Original Files Remain Untouched:**
   - [jarvis_brain.py](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_brain.py)
   - [jarvis_actions.py](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_actions.py)
   - [jarvis_voice.py](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_voice.py)
   - [jarvis_market.py](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_market.py)
   - [jarvis_workplace.html](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_workplace.html)
   These files are kept intact in the repository root as technical reference.
2. **Adapter Layer (`agents/jarvis_agent.py`):**
   `JarvisAgent` acts as an adapter around Jarvis's core persona, deterministic site routing, and calculation concepts, exposing them through the unified `Agent` interface.
3. **Security Invariant:**
   `JarvisAgent` is never granted direct shell or operating system access. Any request for OS execution must pass through the security gate.
