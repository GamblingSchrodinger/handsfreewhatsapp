"""
TTS Engine: Natural Text-to-Speech synthesizer using Edge-TTS with pyttsx3 offline fallback.
"""
import asyncio
import os
import tempfile
import time
import threading
import edge_tts
import pygame
import pyttsx3
import config

# Initialize pygame mixer once
try:
    pygame.mixer.init()
except Exception as e:
    print(f"[TTS] Warning: pygame mixer init error: {e}")

_tts_lock = threading.Lock()
_stop_requested = False


def _speak_robotic(text: str):
    """Speaks using the classic mechanical robotic synthesizer (Microsoft David)."""
    try:
        engine = pyttsx3.init()
        rate = getattr(config, "ROBOTIC_RATE", 185)
        engine.setProperty("rate", rate)
        voices = engine.getProperty("voices")
        for v in voices:
            if "david" in v.name.lower() or "male" in v.name.lower():
                engine.setProperty("voice", v.id)
                break
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[Robotic TTS Error] {e}")


def _speak_pyttsx3_fallback(text: str):
    """Local offline TTS fallback."""
    _speak_robotic(text)


async def _generate_edge_tts(text: str, output_path: str, voice: str):
    """Generate MP3 audio file using Edge-TTS."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def speak(text: str, block: bool = True):
    """
    Speaks the given text.
    If block=True, waits until speech has finished playing before returning.
    """
    if not config.ENABLE_TTS or not text.strip():
        return

    def _play_task():
        global _stop_requested
        _stop_requested = False
        with _tts_lock:
            if getattr(config, "TTS_MODE", "robotic") == "robotic":
                _speak_robotic(text)
                return

            temp_file = None
            try:
                # Generate unique temp file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                    temp_file = fp.name

                # Run async edge-tts generation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        asyncio.wait_for(
                            _generate_edge_tts(text, temp_file, config.TTS_VOICE),
                            timeout=6.0
                        )
                    )
                finally:
                    loop.close()

                # Play via pygame
                if not _stop_requested and os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy() and not _stop_requested:
                        time.sleep(0.05)
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()

            except Exception as edge_err:
                print(f"[TTS] Edge-TTS notice ({edge_err}), using local voice fallback...")
                _speak_pyttsx3_fallback(text)
            finally:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass

    if block:
        _play_task()
    else:
        t = threading.Thread(target=_play_task, daemon=True)
        t.start()


def stop_speaking():
    """Interrupts any currently playing speech."""
    global _stop_requested
    _stop_requested = True
    try:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
    except Exception:
        pass


if __name__ == "__main__":
    print("[TTS Test] Speaking test announcement...")
    speak("Hello Akarsh! Voice assistant is ready to read messages from Keerthana.")
    print("[TTS Test] Completed successfully.")
