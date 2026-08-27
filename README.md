# ASTRA — Personal AI Assistant for Windows

![ASTRA Assistant](https://img.shields.io/badge/ASTRA-v1.0.0_Release-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.10%2B-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg)
![License](https://img.shields.io/badge/license-MIT-purple.svg)

**ASTRA** is an intelligent, voice-enabled, desktop-integrated personal AI assistant designed specifically for Windows. Built with modern Python, PySide6 desktop GUI, Voice Intelligence (STT/TTS/VAD), an extensible LLM Brain reasoning engine, advanced computer & filesystem controls, internet web research capabilities, long-term persistent memory context, vision perception, bounded autonomous task execution, controlled proactive personal automation, and production-grade security, secret redaction, prompt injection defense, and crash recovery.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Operating System**: Windows 10 / Windows 11
- **Python**: Python 3.10 or higher

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/VishwaAdarsh/ASTRA-VOICE.git
cd ASTRA-VOICE

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Running ASTRA
```powershell
# Launch PySide6 Desktop GUI Interface
python main.py

# Launch Interactive Terminal CLI Interface
python main.py --cli

# Display Version Metadata
python main.py --version
```

---

## 🌟 Feature Breakdown (Phases 1 – 12 Completed)

1. **Voice Intelligence**: Hands-free voice activation, microphone STT, pyttsx3 TTS, and VAD audio pipeline.
2. **PySide6 Desktop GUI**: Modern dark-themed dashboard with stacked views (Assistant, Activity, Tools, Memory, Vision, Tasks, Automations, Settings).
3. **LLM Brain Engine**: Multi-provider LLM integration (Mock, OpenAI, Anthropic, Ollama) with rule-based fallback.
4. **Computer & File Control**: Search, inspect, create, move, copy, rename, delete, organize files, and manage Windows apps.
5. **Web Intelligence**: Search web sources, fetch webpages, extract text, and compile structured research summaries.
6. **Memory & Context**: Long-term SQLite knowledge base with automatic expiration policies and privacy deletion tools.
7. **Vision & Screen Inspector**: Capture screens and active windows, detect visual UI elements, extract OCR text, and interpret error messages.
8. **Autonomous Task Engine**: High-level goal decomposition into multi-step execution plans, verification checks, and emergency stop.
9. **Proactive Automation**: Scheduled reminders, condition watches, quiet hours (`23:00 - 07:00`), notifications center, and emergency stop.
10. **Security & Privacy**: Zero-trust prompt injection defense, secret redaction filter, startup crash recovery, `SECURITY.md`, and `PRIVACY.md`.

---

## 🛡️ Security & Privacy
- **[SECURITY.md](SECURITY.md)**: Details the security hierarchy, permission model, and formal threat matrix (T1 – T15).
- **[PRIVACY.md](PRIVACY.md)**: Details data retention, local storage policies, zero hidden surveillance guarantees, and user deletion controls.

---

## 📄 License
Released under the MIT License.
