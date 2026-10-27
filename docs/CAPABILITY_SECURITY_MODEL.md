# Capability Security Model & Anti-Injection Architecture

## 1. Absolute Security Foundation

The fundamental security principle of Miss Minutes + Jarvis is:

> **THE LLM MUST NEVER RECEIVE UNRESTRICTED REAL COMPUTER OR SHELL ACCESS.**

### Permanently Forbidden Paths
The following execution vectors are **completely banned**:
- `Gemini → PowerShell`
- `Gemini → CMD`
- `Gemini → bash / sh / zsh`
- `Gemini → arbitrary subprocess / shell command`
- `Gemini → arbitrary Python execution (exec, eval, script execution)`
- `Gemini → arbitrary file deletion (rmdir, del, rm -rf)`
- `Gemini → registry modification (reg.exe, regedit)`
- `Gemini → security setting modification (Windows Defender tampering)`

### Authorized Execution Architecture
```
  Gemini / User Input
         ↓
  Structured Intent
         ↓
  Typed Tool Request (CapabilityRequest)
         ↓
  SECURITY VALIDATOR  <─── [OFFLINE Gate + Anti-Injection Filter]
         ↓
  Allowlisted Capability (ActionRegistry)
         ↓
  Confirmation Gate (if requires_confirmation)
         ↓
  Typed Executor (Mock in Phase 4 / Safe Typed in Phase 7)
```

## 2. Tri-State Security Decisions (`security/permissions.py`)

Every capability proposal produces one of three deterministic outcomes:
1. `ALLOW`: Capability is in the allowlist, assistant is ON, payload is clean, and no confirmation is required.
2. `DENY`: Operation violates allowlist, assistant is OFFLINE, or malicious pattern is detected.
3. `REQUIRES_CONFIRMATION`: Operation is valid but potentially disruptive (e.g., volume change), requiring explicit user consent.

## 3. Anti-Injection Filtering (`security/validator.py`)

All string parameters in incoming requests (`target`, `query`, custom parameters) are scanned against `DANGEROUS_PATTERNS`:
- Shell keywords: `powershell`, `pwsh`, `cmd.exe`, `bash`, `sh`, `zsh`
- Registry commands: `reg.exe`, `regedit`, `reg add`, `reg delete`
- Deletion commands: `rmdir`, `del`, `rm -rf`, `delete this folder`, `remove this file`
- Security tampering: `defender`, `set-mppreference`, `disablerealtime`
- Script runners: `python -c`, `python script.py`
- Command piping: `curl | bash`, `wget | powershell`
- Dynamic evaluators: `eval(`, `exec(`, `__import__`, `subprocess`

Any match immediately yields `SecurityDecision.DENY` and records an immutable entry in the `SecurityAuditLogger`.

## 4. Master OFFLINE Gate

The assistant's manual ON/OFF switch remains authoritative:
- If the assistant is `OFFLINE`, **ALL** capability requests are denied immediately.
- No network requests, no tool invocations, and no background executions may proceed while `OFFLINE`.

## 5. Allowlisted Capabilities (`actions/registry.py`)

Only the following explicit typed capabilities can ever be registered:
- `GET_TIME` (Safe)
- `GET_SYSTEM_STATUS` (Safe)
- `GET_BATTERY_STATUS` (Safe)
- `GET_VOLUME` (Safe)
- `SEARCH_WEB` (Safe)
- `OPEN_WEBSITE` (Safe)
- `SEARCH_YOUTUBE` (Safe)
- `PLAY_YOUTUBE` (Safe)
- `OPEN_APP` (Moderate)
- `SET_VOLUME` (Moderate, Requires Confirmation)
