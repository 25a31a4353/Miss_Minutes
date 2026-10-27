# ⏰ Miss Minutes & Jarvis AI Desktop Assistant

> **An Intelligent Dual-Agent Desktop Assistant for Windows 10/11.**  
> Powered by Real LLMs (Google Gemini, OpenAI, Groq, Hugging Face, Free Intelligence), Adaptive Telugu-English Context Learning, Zero-Lag Audio Caching, Hands-Free Voice VAD, Screen Reading, and Desktop Automation.

---

## 🌟 Highlights & Capabilities

- 🗣️ **Conversational Turn-Taking Dialogue**: Miss Minutes and Jarvis take sequential, non-overlapping turns speaking. Miss Minutes greets you with her charming, witty TVA companion personality, and Jarvis continues the conversation with crisp, authoritative execution confirmation.
- 🇮🇳 **Modern Telugu + English ("Tenglish")**: Native Telugu speech recognition and Edge-TTS neural speech (`te-IN-ShrutiNeural` for Miss Minutes, `te-IN-MohanNeural` for Jarvis). Supports code-switching without forced translation.
- 🧠 **Adaptive Context & NLP Learning**: The `ContextLearner` dynamically observes your speech habits, learns your favorite Telugu idioms and Tenglish phrasing (e.g., *"workload"*, *"seconds lo"*, *"cheyyi"*, *"choodu"*), remembers personal facts, and learns custom aliases (e.g., *"wa ante whatsapp"*).
- ⚡ **Zero-Lag Architecture**:
  - **In-Memory Audio Cache**: Frequently spoken greetings, confirmations, volume acknowledgments, and standby notifications play back with **0ms synthesis latency**.
  - **Concurrent Rapid Research**: Parallel queries across Wikipedia and DuckDuckGo with in-memory caching for sub-second answers.
- 🎙️ **Hands-Free Continuous Listening**: Real-time RMS voice activity detection (VAD) with automatic 0.85s silence termination. Say *"remain quiet"* or *"silent ga undu"* to put the assistants in quiet standby mode until asked to wake.
- 🚀 **Multi-Provider LLM Intelligence**:
  - **Google Gemini**: `gemini-2.5-flash` / `gemini-2.0-flash`
  - **OpenAI**: `gpt-4o-mini`, `gpt-4o`, or local **Ollama** (`http://localhost:11434/v1`)
  - **Groq Cloud**: `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` (800+ tokens/sec)
  - **Hugging Face Hub**: Serverless Inference API for open-access models (`Llama-3.3-70B`, `Qwen-2.5-72B`)
  - **Free Public AI**: Key-free instant inference engine ensuring real LLM capability with zero mandatory setup
- 🖥️ **Desktop Capabilities**:
  - **Google Chrome**: Browser launching, URL navigation, search, and tab handling.
  - **WhatsApp**: Desktop protocol (`whatsapp://`) with automatic fallback to [web.whatsapp.com](https://web.whatsapp.com).
  - **Screen Reader**: Primary display capture and Windows Media OCR to read questions, code, and documents directly off your screen.
  - **System Audio Controls**: Master volume up, down, mute, and direct percentage setting.

---

## 🚀 Quick Start

### 1. Requirements & Installation

Requires Python 3.10+ (tested on Python 3.14 on Windows).

```powershell
# Clone the repository
git clone https://github.com/25a31a4353/Miss_Minutes.git
cd Miss_Minutes

# Install production dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration (Optional)

Copy `.env.example` to `.env` to configure your preferred AI provider:

```env
# Primary Provider: Google Gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash

# OpenAI & OpenAI-Compatible (Ollama, LM Studio, OpenRouter)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
# OPENAI_BASE_URL=http://localhost:11434/v1

# Groq High-Speed Cloud Inference
GROQ_API_KEY=your_groq_key

# Hugging Face Serverless Inference
HF_TOKEN=your_huggingface_token
HF_MODEL=meta-llama/Llama-3.3-70B-Instruct
```

> **Note**: An API key is **never required** to launch and use Miss Minutes & Jarvis! The built-in Free Intelligence Provider automatically handles queries if no API key is supplied.

### 3. Running the Assistant

```powershell
# Start the full desktop assistant with hands-free listening
python main.py

# Or launch via batch script
launch_miss_minutes.bat
```

---

## 🎙️ Voice & Spoken Interactions Cheat-Sheet

| What You Say (Telugu / English) | How Miss Minutes & Jarvis Respond | Action Executed |
| :--- | :--- | :--- |
| *"Hey Miss Minutes, ivala chala workload undhi"* | **Miss Minutes**: *"Enti ivala chala workload undhi anukunta darling! Neeku eh help kavalo cheppu seconds lo complete chesi pedathanu!"*<br/>**Jarvis**: *"Standing by sir. Chrome, WhatsApp, screen research, system actions — edhaina ready ga undhi."* | Turn-taking greeting & readiness confirmation |
| *"Open Chrome and search for machine learning"* | **Miss Minutes**: *"Searching machine learning for you sugar!"*<br/>**Jarvis**: *"Web navigation dispatched, sir."* | Launches Chrome & conducts search |
| *"Open WhatsApp"* | **Miss Minutes**: *"Opening WhatsApp for you darling!"*<br/>**Jarvis**: *"Application launched, sir."* | Launches WhatsApp desktop (or Web fallback) |
| *"Read my screen"* or *"Screen meedha emundhi"* | **Miss Minutes**: *"Scanning your active window right away sugar!"*<br/>**Jarvis**: *"Active window analyzed. Content verified, sir."* | PySide6 + OCR screen capture & analysis |
| *"Quantum computing ante enti research chesi cheppu"* | **Miss Minutes**: *"Manchi question sugar! Jarvis research details share chestharu choodandi."*<br/>**Jarvis**: *"Here are the verified research findings, sir..."* | Concurrent Wikipedia + DuckDuckGo + LLM synthesis |
| *"Volume 80 ki set cheyyi"* | **Miss Minutes**: *"Volume 80% ki set chesanu sugar!"*<br/>**Jarvis**: *"Master audio level adjusted, sir."* | Sets system volume via PyCAW |
| *"Remain quiet"* / *"Silent ga undu"* / *"Aagu"* | **Miss Minutes**: *"Sare darling, nenu silent ga untanu."*<br/>**Jarvis**: *"Standing by quietly, sir. Call whenever you need us."* | Enters quiet standby mode |
| *"wa ante whatsapp"* | **Miss Minutes**: *"Got it sugar! I've learned that shortcut."* | ContextLearner records custom alias |

---

## 🧪 Verification & Diagnostics

Miss Minutes & Jarvis include a comprehensive test suite guaranteeing production reliability:

```powershell
# Run system diagnostics (verifies 6/6 core subsystems)
python main.py --diagnostics

# Run the complete automated test suite (185 tests)
python -m pytest tests/ -q
```

---

## 🛡️ Security Architecture

The application strictly enforces a **Default-DENY Security Gate** ([security/validator.py](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/security/validator.py)):
- **No Arbitrary Shell Execution**: Raw Command Prompt, PowerShell commands, and script execution are strictly prohibited.
- **Application Allowlisting**: Only verified executables (Chrome, Edge, WhatsApp, Spotify, VS Code, Notepad, Calculator) are permitted to launch.
- **Path Traversal Protection**: System directories and unauthorized sensitive paths are permanently blocked.
- **Offline Gate Authority**: When the assistant is in `OFFLINE` state, all microphone listening, speech synthesis, and capability dispatch are hardware-isolated and blocked.

---

## 📄 Documentation & PDF Guides

- **Setup & Multilingual Architecture Guide**: [Jarvis_Setup_Guide.pdf](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/Jarvis_Setup_Guide.pdf)
- **Product Requirements Document**: [Miss_Minutes_PRD.md](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/Miss_Minutes_PRD.md)
- **Architecture & Security Specifications**: See [docs/](file:///c:/Users/SHANMUKHESWAR/OneDrive/Desktop/Miss_minutes/Jarvis/docs/)
