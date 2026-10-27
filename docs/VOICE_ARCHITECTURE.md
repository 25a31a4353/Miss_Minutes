# Voice Interaction Architecture — Miss Minutes + Jarvis

## 1. Overview & Core Contract

The voice subsystem provides safe technical interfaces for Speech-to-Text (STT), Text-to-Speech (TTS), and local wake-word detection.

> **CRITICAL PHASE 4 CONSTRAINT**:
> Continuous microphone capture, continuous wake-word listening threads, and automatic audio playback are **INTENTIONALLY NOT ACTIVATED** in Phase 4.
> All voice components in Phase 4 are structured abstractions accompanied by deterministic test mocks.

```
                         MASTER OFFLINE GATE
                                  │
                   ┌──────────────┴──────────────┐
             ONLINE│                             │OFFLINE
                   ▼                             ▼
       ┌──────────────────────┐        ┌──────────────────────┐
       │     VoiceService     │        │ All Voice Operations │
       │  - transcribe_audio  │        │   STRICTLY BLOCKED   │
       │  - speak_text        │        │   (PermissionError)  │
       │  - start/stop_wake   │        └──────────────────────┘
       └──────────┬───────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
       STT       TTS    WAKE WORD
    (Whisper) (Edge/Gem) (Hey Minutes)
```

## 2. Speech-to-Text (STT) Layer (`voice/stt.py`)

- **Primary Engine**: `faster-whisper`.
- **Abstraction**: `SpeechToTextProvider`.
- **Multilingual Support**:
  - English (`en`)
  - Telugu (`te`)
  - Code-Switching (`te-en`)
- **Safety Invariant**:
  - Transcription task is strictly set to `"transcribe"`, **NEVER** `"translate"`.
  - The original transcript is preserved verbatim without forced translation into English before intent analysis.
- **Mock Provider**: `MockSTTProvider` allows tests to set mock transcripts without loading weights or touching microphones.

## 3. Text-to-Speech (TTS) Layer (`voice/tts.py` & `voice/voices.py`)

- **Primary Candidate**: Gemini Speech Generation / Gemini TTS.
- **Fallback**: Microsoft Edge TTS (`edge-tts`).
- **Distinct Voice Profiles**:
  The system **strictly prohibits** Miss Minutes and Jarvis sharing the same voice.
  - **Miss Minutes**:
    - Gender: Female
    - Character: Warm, cheerful, witted Southern clock companion
    - English Voice: `en-US-JennyNeural` (+5Hz pitch, +5% rate)
    - Telugu Voice: `te-IN-ShrutiNeural`
  - **Jarvis**:
    - Gender: Male
    - Character: Composed, dry wit, impeccable professional co-pilot
    - English Voice: `en-GB-RyanNeural` (-2Hz pitch)
    - Telugu Voice: `te-IN-MohanNeural`
- **Mock Provider**: `MockTTSProvider` generates synthetic silent WAV headers for testing audio pipelines without hardware devices.

## 4. Wake-Word Detection (`voice/wake.py`)

- **Target Phrase**: `"Hey Minutes"`.
- **Processing Boundary**: Strictly local acoustic detection. No audio is ever streamed to external endpoints for wake-word evaluation.
- **CRITICAL SECURITY INVARIANT**:
  > **Wake-word detection is NOT authentication.**
  > Hearing "Hey Minutes" confirms an acoustic prompt trigger only; it does NOT authenticate user identity or grant elevated privileges.
- **Mock Implementation**: `MockWakeWordDetector` supports deterministic `simulate_wake(timestamp)` without opening background threads or hardware streams.

## 5. Master OFFLINE Gate (`voice/service.py`)

If the assistant state is `OFFLINE`:
- `transcribe_audio()` raises `PermissionError` immediately.
- `speak_text()` raises `PermissionError` immediately.
- `start_wake_detection()` raises `PermissionError` immediately.
- Switching to `OFFLINE` automatically calls `stop()` on any active wake detectors.

## 6. Future Activation Points (Phase 5)

In Phase 5 (Real Voice Layer):
1. Download small `faster-whisper` quantized model weights (`tiny` or `base`).
2. Integrate PyAudio / sounddevice for real-time ring-buffer audio capture.
3. Activate openWakeWord or Porcupine local model for "Hey Minutes".
4. Route synthesized audio streams to local speakers via Qt multimedia or sounddevice.
