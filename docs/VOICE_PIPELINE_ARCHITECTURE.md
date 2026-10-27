# Real Voice Pipeline Architecture — Miss Minutes + Jarvis

## 1. Overview & Architectural Principles

Phase 5 introduces the real voice interaction layer for Miss Minutes + Jarvis on Windows 11.
The subsystem orchestrates microphone speech capture, local acoustic wake-word triggering, multilingual `faster-whisper` speech-to-text, agent response synthesis, and audio playback through speakers.

```text
                           ┌────────────────────────────┐
                           │   WINDOWS AUDIO HARDWARE   │
                           │  Microphone Array / WASAPI │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │      MicrophoneDevice      │
                           │  - 16kHz Mono 16-bit PCM   │
                           │  - In-Memory WAV Packaging │
                           │  - Timeout-guarded Capture │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │   AcousticWakeWordDetector │
                           │   Detects "Hey Minutes"    │
                           │  (STRICTLY NON-AUTH PROMPT)│
                           └─────────────┬──────────────┘
                                         │ Trigger Event
                                         ▼
                           ┌────────────────────────────┐
                           │       AppStateMachine      │
                           │  WAKE_DETECTED → LISTENING │
                           └─────────────┬──────────────┘
                                         │ Speech Audio Bytes
                                         ▼
                           ┌────────────────────────────┐
                           │  FasterWhisperSTTProvider  │
                           │  - CTranslate2 Model Tiny  │
                           │  - English, Telugu, te-en  │
                           │  - Silence Activity Guard  │
                           │  - Verbatim Transcript     │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │      AppStateMachine       │
                           │        TRANSCRIBING        │
                           └─────────────┬──────────────┘
                                         │ Verbatim Transcript
                                         ▼
                           ┌────────────────────────────┐
                           │    CapabilityPipeline      │
                           │  IntentParser (te-en/en)   │
                           │            ↓               │
                           │  Miss Minutes ↔ Jarvis     │
                           │  SecurityValidator (ALLOW) │
                           │  Allowlisted Tool Executor │
                           └─────────────┬──────────────┘
                                         │ Response Text
                                         ▼
                           ┌────────────────────────────┐
                           │       AppStateMachine      │
                           │      WORKING → SPEAKING    │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │    TextToSpeechProvider    │
                           │  - Miss Minutes: Female    │
                           │    (en-US-JennyNeural /    │
                           │     te-IN-ShrutiNeural)    │
                           │  - Jarvis: Male (British)  │
                           │    (en-GB-RyanNeural /     │
                           │     te-IN-MohanNeural)     │
                           └─────────────┬──────────────┘
                                         │ Synthesized MP3/WAV
                                         ▼
                           ┌────────────────────────────┐
                           │        AudioPlayer         │
                           │  QMediaPlayer / winsound   │
                           │   Speakers / Real Output   │
                           └─────────────┬──────────────┘
                                         │
                                         ▼
                           ┌────────────────────────────┐
                           │       AppStateMachine      │
                           │       SUCCESS → IDLE       │
                           └────────────────────────────┘
```

---

## 2. Core Components

### 1. Windows Microphone Capture (`voice/microphone.py`)
- **Engine**: Native Windows Core Audio / WASAPI through `PySide6.QtMultimedia` with safe fallback buffer.
- **Specifications**: 16,000 Hz sample rate, 1 channel (mono), 16-bit signed integer PCM.
- **WAV Packaging**: In-memory standard RIFF/WAV header generation via `create_wav_bytes`.
- **Safety Invariant**:
  - Strictly refuses capture when assistant is `OFFLINE` (`PermissionError`).
  - Switching `OFF` during active recording terminates recording and releases device buffers immediately.
  - Timeout-guarded phrase capture guarantees return without blocking the Qt UI thread.

### 2. Speech-to-Text (`voice/stt.py`)
- **Engine**: `faster-whisper` (CTranslate2 4.8.3 runtime).
- **Default Model**: `Systran/faster-whisper-tiny` (quantized int8 on CPU).
- **Language Coverage**:
  - English (`en`)
  - Telugu (`te`)
  - Telugu-English Code-Switching (`te-en`)
- **Key Invariants**:
  - `task="transcribe"`: **Never** force-translates Telugu to English before intent analysis.
  - Raw verbatim transcript is preserved.
  - Voice Activity Detection (VAD) filter and silence guard: inaudible or silent audio produces `raw_text=""` and `confidence=0.0`. It **never** hallucinates commands on background silence.

### 3. Local Wake-Word Trigger (`voice/wake.py`)
- **Target Phrase**: `"Hey Minutes"`.
- **Acoustic Detection**: `AcousticWakeWordDetector` running in a managed daemon worker thread.
- **CRITICAL SECURITY RULE**:
  > Wake-word detection is **NOT authentication**. Hearing "Hey Minutes" triggers the assistant into `LISTENING` mode; it does NOT grant elevated privileges or authenticate identity.

### 4. Text-to-Speech & Real Speaker Playback (`voice/tts.py` & `voice/audio_player.py`)
- **TTS Engine**: `EdgeTTSProvider` using Microsoft neural multilingual voices.
- **Distinct Voice Personas**:
  - **Miss Minutes**: Female, warm, lively Southern clock companion (`en-US-JennyNeural` / `te-IN-ShrutiNeural`).
  - **Jarvis**: Male, composed, dry-witted British co-pilot (`en-GB-RyanNeural` / `te-IN-MohanNeural`).
- **Speaker Playback**: `AudioPlayer` manages hardware playback via `PySide6.QtMultimedia.QMediaPlayer` / `QAudioOutput` and Windows `winsound`.
- **Safety Invariant**: When assistant is `OFFLINE`, audio playback is strictly blocked and active audio streams are purged immediately.

---

## 3. Authoritative Single Jarvis Invariant

```text
COUNT(JARVIS_IMPLEMENTATIONS) = 1
```
Jarvis's voice interaction is routed through the single authoritative Jarvis implementation:
- [`jarvis_voice.py`](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/jarvis_voice.py) coordinates with the shared `VoiceService`.
- When Jarvis speaks, he uses his distinct male British profile (`en-GB-RyanNeural` / `te-IN-MohanNeural`).
- Jarvis proposals pass through `SecurityValidator` before execution.
