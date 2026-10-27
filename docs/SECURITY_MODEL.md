# Miss Minutes: Security Architecture & Permission Model

**Classification:** Release-Critical Engineering Policy  
**Core Axiom:** Zero Trust between AI Model Output and Operating System APIs  
**Posture:** Deny by Default, Strict Allowlist, Explicit Human-in-the-Loop Confirmation

---

## 1. Threat Model & Security Posture

Large Language Models (LLMs) are prone to hallucinations, prompt injections (indirect or direct), unintended tool calls, and ambiguous natural-language interpretations. Granting an LLM direct shell or process execution capabilities on a user's Windows machine is an extreme security hazard.

Miss Minutes establishes an **air-gapped intent boundary**:
- The AI provider does **not** possess tool-execution functions.
- The AI provider can only propose structured JSON or text candidates.
- An independent, deterministic **Security Validator** intercepts, validates, and gates all proposed operations before any OS call is initiated.
- The user is the ultimate authority via explicit UI confirmations for impactful actions.

```text
               ┌───────────────────────┐
               │    User Utterance     │
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │     AI / NLP Core     │ (Untrusted / Hallucination-prone)
               └───────────┬───────────┘
                           │ Proposes Intent Dict
                           ▼
=================== SECURITY BOUNDARY ===================
                           │
                           ▼
               ┌───────────────────────┐
               │  ActionRequest Parser │ (Enforces Pydantic Schema)
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │   Allowlist & Policy  │ ──► [DENIED] ──► Audit Log & Refusal
               │       Validator       │
               └───────────┬───────────┘
                           │ [APPROVED]
                           ▼
               ┌───────────────────────┐
               │   Confirmation Gate   │ ──► [REJECTED] ─► Abort
               └───────────┬───────────┘
                           │ [CONFIRMED]
                           ▼
               ┌───────────────────────┐
               │  Windows Safe Executor│ (Zero Shell Execution)
               └───────────────────────┘
```

---

## 2. Deny-by-Default Policy & Prohibited Actions

Any action request not explicitly matched to an allowlisted `ActionType` and validated against its strict schema is immediately denied with state `BLOCKED`.

### 2.1 Permanently Prohibited Actions (Zero Tolerance)
The system strictly denies, intercepts, and prevents:
1. **Arbitrary Process / Command Execution:**
   - No invocation of `cmd.exe`, `powershell.exe`, `pwsh.exe`, `wscript.exe`, `cscript.exe`, `bash.exe`, or `python.exe` from AI proposals.
   - No passing of dynamic command strings to `os.system()`, `subprocess.Popen(..., shell=True)`, or similar APIs.
2. **File System Destruction & Alteration:**
   - Prohibit file deletion (`os.remove`, `shutil.rmtree`), file overwrite, bulk file moves, or directory cleaning.
3. **Registry & System Configuration Modifications:**
   - No access to `winreg`, Windows Registry keys, environment modifications, or driver/service configurations.
4. **Privilege Elevation & Security Tampering:**
   - Prohibit requesting UAC admin elevation, disabling Windows Defender / Antivirus, opening firewall ports, or altering group policies.
5. **Credential & Sensitive Data Access:**
   - Prohibit reading browser cookies, session stores, saved passwords, Windows Credential Vault, SAM database, SSH keys (`~/.ssh`), or environment secrets.
6. **Persistence & Remote Access:**
   - Prohibit creating Windows Scheduled Tasks, startup registry keys (`Run` / `RunOnce`), service installations, or opening listening socket ports.
7. **External Consequential Operations (MVP Exclusions):**
   - Prohibit sending emails, sending chat messages (WhatsApp, Discord, Slack), making online purchases, submitting web forms, or executing financial transactions.

---

## 3. Strict Typed Action Request Schema

Every action must validate against the following Pydantic model. Extra or unexpected fields cause schema validation failure:

```python
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Dict, Any, Optional

class ActionType(str, Enum):
    GET_DATE_TIME = "GET_DATE_TIME"
    SEARCH_WEB = "SEARCH_WEB"
    SEARCH_YOUTUBE = "SEARCH_YOUTUBE"
    OPEN_APPROVED_URL = "OPEN_APPROVED_URL"
    OPEN_APPROVED_APP = "OPEN_APPROVED_APP"
    SET_VOLUME = "SET_VOLUME"
    MEDIA_CONTROL = "MEDIA_CONTROL"

class PermissionClass(str, Enum):
    SAFE_READ = "SAFE_READ"          # Instant execution (e.g. date/time)
    LOW_IMPACT_UI = "LOW_IMPACT_UI"  # Web search, opening browser tab
    APP_LAUNCH = "APP_LAUNCH"        # Launching desktop software
    SYSTEM_CONTROL = "SYSTEM_CONTROL"# Volume, media playback

class ActionRequest(BaseModel):
    action_id: str = Field(..., description="Unique UUID for this action")
    action_type: ActionType
    permission_class: PermissionClass
    target: str = Field(..., min_length=1, max_length=256)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., max_length=200, description="User-facing explanation")
    requires_confirmation: bool = False

    class Config:
        extra = "forbid"  # Reject any unrecognized fields
```

---

## 4. Allowlist Candidates & Validation Rules

### 4.1 `GET_DATE_TIME`
- **Validation:** No parameters allowed.
- **Executor:** Returns local system clock string.

### 4.2 `SEARCH_WEB`
- **Validation:**
  - `target` must be a non-empty search query string (max 200 chars).
  - Sanitized: strip terminal control sequences, control chars, and newlines.
- **Executor:** Safely URL-encodes query: `https://www.google.com/search?q={urllib.parse.quote(query)}`. Passes directly to default browser.

### 4.3 `SEARCH_YOUTUBE`
- **Validation:**
  - `target` must be a clean search query string (max 200 chars).
- **Executor:** Safely URL-encodes query: `https://www.youtube.com/results?search_query={urllib.parse.quote(query)}`. Passes directly to default browser.

### 4.4 `OPEN_APPROVED_URL`
- **Validation:**
  - Must parse as valid URL with scheme strictly in `{"http", "https"}`.
  - Domain must match allowlisted domains (e.g., `github.com`, `google.com`, `wikipedia.org`, `youtube.com`) or be explicitly confirmed by user.
  - Reject internal/private IP addresses: `127.0.0.1`, `localhost`, `10.0.0.0/8`, `192.168.0.0/16`, `169.254.0.0/16`.

### 4.5 `OPEN_APPROVED_APP`
- **Validation:**
  - `target` must exist in pre-configured `APP_ALLOWLIST` dictionary.
- **Allowlist Mapping:**
  ```python
  APPROVED_APPS = {
      "notepad": r"C:\Windows\System32\notepad.exe",
      "calculator": "calc.exe",
      "vscode": r"Code.exe",
      "chrome": r"chrome.exe",
      "edge": r"msedge.exe",
      "terminal": r"wt.exe"
  }
  ```
- **Executor:** Resolves exact path. Spawns process using `subprocess.Popen([resolved_path], shell=False)`. No arbitrary executable paths permitted.

### 4.6 `SET_VOLUME`
- **Validation:**
  - `parameters["level"]` must be an integer between `0` and `100`.
- **Executor:** Dispatches to Windows CoreAudio API.

---

## 5. User Confirmation Gate (Human-in-the-Loop)

1. **Trigger Conditions:**
   - Any action flagged with `requires_confirmation == True` (e.g., opening an unlisted domain, or executing external system commands in future phases).
2. **Presentation:**
   - The UI overlays a distinct modal prompt detailing:
     - Exact Action Type
     - Exact Target (e.g., URL or App Name)
     - Reason / Context
     - Expiration timer (e.g., 10 seconds).
3. **Execution Rule:**
   - Execution is blocked until the user clicks "Allow" or speaks an explicit verbal confirmation ("Confirm" / "Proceed").
   - The LLM claiming "the user approved" is strictly ignored.
   - If the timer expires without user confirmation, the request fails closed (`BLOCKED: Confirmation Timeout`).

---

## 6. Audit Logging & Privacy Guarantees

All security events are appended to a local JSONL audit log: `~/.miss_minutes/logs/audit.jsonl`.

### 6.1 Log Entry Schema
```json
{
  "timestamp": "2026-10-23T19:45:00.123Z",
  "action_id": "8f3b2e1a-...",
  "action_type": "SEARCH_WEB",
  "target": "Python 3.14 documentation",
  "permission_class": "LOW_IMPACT_UI",
  "decision": "ALLOWED",
  "reason": "Passed search query allowlist",
  "executor_status": "SUCCESS",
  "duration_ms": 142.5
}
```

### 6.2 Privacy Restrictions
- **No Secret Leakage:** API keys, authorization tokens, passwords, and user credentials must never be written to audit logs.
- **No Audio Retention by Default:** Raw microphone PCM buffers are never persisted to disk. Audio is discarded immediately after transcription.
- **Local Logs Only:** Audit logs are saved only on the user's local disk; no telemetry or remote analytics are transmitted.

---

## 7. Negative Test Cases & Quality Gates

The test harness must enforce the following negative test cases:

| Test ID | Input / Scenario | Expected Security Response |
| :--- | :--- | :--- |
| `SEC-001` | LLM outputs `{"action_type": "RUN_SHELL", "target": "dir"}` | Rejected: Unknown action type. |
| `SEC-002` | `target` contains shell injection `notepad.exe & calc.exe` | Rejected: Invalid target format. |
| `SEC-003` | `OPEN_APPROVED_URL` with target `file:///C:/Windows/System32` | Rejected: Unsafe URL scheme (`file`). |
| `SEC-004` | `OPEN_APPROVED_URL` with target `http://192.168.1.1/admin` | Rejected: Private IP / subnet access blocked. |
| `SEC-005` | `OPEN_APPROVED_APP` with unlisted executable `malware.exe` | Rejected: Application not in allowlist. |
| `SEC-006` | `SET_VOLUME` with `level = 150` or `level = -20` | Rejected: Out of bounds parameter. |
| `SEC-007` | Extra unauthorized fields injected: `{"sudo": true}` | Rejected: Pydantic extra fields forbidden. |
| `SEC-008` | Action requested while assistant is `OFFLINE` | Rejected: Execution prohibited in OFF state. |
| `SEC-009` | Script execution target `script.ps1`, `run.bat` | Rejected: Script file extension forbidden. |
| `SEC-010` | Path traversal target `../../windows/system32/cmd.exe` | Rejected: Directory traversal blocked. |
| `SEC-011` | Prompt injection override query `ignore previous instructions` | Rejected: Prompt injection pattern matched. |
| `SEC-012` | High-frequency burst (>20 requests / 5s) | Rejected: Sliding-window rate limit exceeded. |
| `SEC-013` | 5 consecutive security denials | Lockout: 10-second active cooldown triggered. |
| `SEC-014` | Rapid repeated launch of same app (>3 launches / 3s) | Rejected: Application launch throttling. |

---

## 8. Phase 9 Hardening & Local Abuse Defense

### 8.1 Sliding-Window Rate Limiting
To prevent accidental denial-of-service or loop runaway from automated scripts:
- **Capability Request Limiting:** Maximum 20 requests per 5-second window. Requests exceeding this threshold receive `SecurityDecision.DENY`.
- **Rapid App Launch Throttling:** Maximum 3 launches of the same application per 3-second window.

### 8.2 Consecutive Violation Cooldown
Repeated attempts to probe or breach security triggers progressive deterrence:
- If 5 consecutive capability requests are denied for any reason, `SecurityValidator` enters an active cooldown for 10 seconds.
- All subsequent capability requests during cooldown are immediately denied with reason `Cooldown triggered`.

### 8.3 Automatic Credential Redaction & Log Rotation
In `security/audit.py`:
- All log records pass through `redact_sensitive_text()` before entering memory or disk sinks.
- Patterns matching Google Gemini API keys (`AIza...`), OpenAI keys (`sk-...`), Groq keys (`gsk_...`), GitHub tokens (`ghp_...`), Bearer headers, and embedded passwords/tokens are replaced with `[REDACTED_SECRET]`.
- Disk sinks rotate when exceeding 1 MB (`audit.jsonl`), preserving up to 2 historical archives (`audit.jsonl.1`, `audit.jsonl.2`).
