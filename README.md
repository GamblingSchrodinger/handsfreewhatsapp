# 🎙️ WhatsApp Voice Assistant ()

An intelligent, hands-free voice automation system for WhatsApp, custom-built for **Khandavalli Akarsh Anirudh**.

Whenever  sends a message on WhatsApp:
1. **Reads Out Aloud**: Your laptop announces her message via high-quality natural Text-to-Speech (*"Keerthana sent: ... Listening for your reply."*).
2. **Listens to You**: Your microphone automatically opens and captures your spoken reply.
3. **Speech-to-Text**: Transcribes your voice into clean text (optimized for Indian English).
4. **Hands-Free Send**: Types your reply directly into her chat and sends it on WhatsApp, then confirms with audio: *"Reply sent to Keerthana."*

---

## 🚀 Quick Start

### 1. Launch the Assistant
Open PowerShell in this folder and run:
```powershell
python main.py
```
Or run in terminal-only mode (without GUI window):
```powershell
python main.py --cli
```

### 2. First-Time WhatsApp Login (One-Time Only!)
1. On the very first run, Chromium will open `web.whatsapp.com`.
2. Open WhatsApp on your phone → **Settings / Three dots** → **Linked Devices** → **Link a Device**.
3. Scan the QR code shown on your laptop screen.
4. **Done!** The session is persistently saved in `./session_data`. You will **never** need to scan the QR code again on future runs.

---

## 🎛️ Control Panel Features

When running `python main.py`, a sleek dark-mode dashboard is displayed:
- **WhatsApp Status**: Live indicator showing `Scan QR Code` or `Connected`.
- **Latest Message Card**: Shows the exact text of the latest incoming message from Keerthana.
- **Voice Reply Card**: Displays your transcribed voice in real time.
- **Auto-Send Countdown**: Gives you a 2.5-second countdown to review before sending (with instant **Send Now** or **Cancel** options).
- **🎙️ Manual Voice Reply**: Click this button at any time to dictate and send a voice reply even without waiting for an incoming message.
- **Test Mic (3s)**: Verifies that your microphone captures and transcribes your voice clearly.
- **Test Speakers / TTS**: Verifies your laptop's audio playback.

---

## ⚙️ Configuration (`config.py`)

You can easily tweak settings in `config.py`:
- `TARGET_CHAT`: Target contact name (default: `"Keerthana Chemical Engineering"`).
- `AUTO_SEND`: `True` to send automatically after speaking, or `False` to require clicking Send.
- `AUTO_SEND_COUNTDOWN`: Delay in seconds (default: `2.5`) to allow reviewing the transcript before sending.
- `READ_INCOMING_ALOUD`: `True` to speak her message out loud.
- `TTS_VOICE`: Neural voice model (default: `"en-IN-NeerjaNeural"`).
- `RECORD_MAX_SECONDS`: Maximum speech listening duration (default: `15`).
- `SILENCE_TIMEOUT_SECONDS`: Duration of silence before stopping recording (default: `1.8`).

---

## 🛠️ Architecture

- **WhatsApp Engine (`whatsapp_bot.py`)**: Playwright Chromium with persistent context (`./session_data`). Monitors the chat DOM for incoming message bubbles (`div.message-in`) and sends messages to the footer input box.
- **Speech-to-Text (`audio_engine.py`)**: Native `sounddevice` stream with RMS-based Voice Activity Detection and silence detection, converting audio to text via `SpeechRecognition` (`en-IN`).
- **Text-to-Speech (`tts_engine.py`)**: Microsoft Edge neural TTS with offline Windows SAPI5 (`pyttsx3`) fallback, played through `pygame.mixer`.
- **GUI Dashboard (`gui_app.py`)**: Native Tkinter dark-mode interface.
