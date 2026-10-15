"""
Configuration settings for WhatsApp Voice Assistant
Target Chat: Keerthana Chemical Engineering
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Target WhatsApp chat/contact name exactly as it appears in your WhatsApp
TARGET_CHAT = "Keerthana Chemical Engineering"

# Persistent browser profile directory to keep WhatsApp logged in
SESSION_DIR = BASE_DIR / "session_data"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Audio / Microphone Settings
SAMPLE_RATE = 16000  # 16kHz standard for speech recognition
CHANNELS = 1         # Mono audio
RECORD_MAX_SECONDS = 15        # Maximum duration to listen per reply
SILENCE_TIMEOUT_SECONDS = 1.8  # Stop recording after this many seconds of silence
ENERGY_THRESHOLD = 300         # Minimum RMS energy to consider as speech

# Speech-to-Text (STT) Settings
STT_LANGUAGE = "en-IN"  # Optimized for Indian English accent ("en-US" fallback)

# Text-to-Speech (TTS) Settings
ENABLE_TTS = True
TTS_MODE = "robotic"               # "robotic" (classic mechanical bot) or "neural"
ROBOTIC_RATE = 185                 # Cadence for robotic voice
TTS_VOICE = "en-IN-PrabhatNeural"  # Used only if TTS_MODE is set to "neural"

# Sending Behavior
AUTO_SEND = True                 # Automatically send transcribed text after countdown
AUTO_SEND_COUNTDOWN = 2.5        # Seconds to review transcribed text before sending
READ_INCOMING_ALOUD = True       # Read Keerthana's incoming messages through speakers

# Browser Options
HEADLESS = False                 # Set to False so you can see WhatsApp Web and scan QR initially
BROWSER_CHANNEL = "msedge"       # Uses Windows 11's native Microsoft Edge (Chromium)
WHATSAPP_WEB_URL = "https://web.whatsapp.com"
