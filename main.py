"""
Main Orchestrator for WhatsApp Voice Assistant (Target: Keerthana Chemical Engineering).
Integrates WhatsApp automation, speech-to-text, text-to-speech, and GUI/CLI control.
"""
import sys
import time
import argparse
import threading
import config
import tts_engine
import audio_engine
from whatsapp_bot import WhatsAppBot
from gui_app import VoiceAssistantGUI

_gui_instance: VoiceAssistantGUI | None = None
_bot_instance: WhatsAppBot | None = None
_is_processing_interaction = False
_interaction_lock = threading.Lock()


def log_status(msg: str):
    line = f"[Orchestrator] {msg}"
    print(line)
    try:
        with open(config.BASE_DIR / "assistant.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
    except Exception:
        pass
    if _gui_instance:
        _gui_instance.log(msg)


def handle_whatsapp_status(status: str):
    line = f"[WhatsApp] {status}"
    try:
        with open(config.BASE_DIR / "assistant.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n")
    except Exception:
        pass
    if _gui_instance:
        _gui_instance.log(line)
        if "connected" in status.lower() or "active" in status.lower():
            _gui_instance.set_whatsapp_status("Connected", state="connected")
        elif "scan" in status.lower():
            _gui_instance.set_whatsapp_status("Scan QR Code", state="warning")
        elif "error" in status.lower():
            _gui_instance.set_whatsapp_status("Error", state="error")
        else:
            _gui_instance.set_whatsapp_status(status[:18], state="normal")


def on_incoming_message(sender: str, text: str):
    """
    Triggered when a new message arrives from Keerthana.
    Executes the voice announcement -> mic capture -> transcription -> send pipeline.
    """
    global _is_processing_interaction
    with _interaction_lock:
        if _is_processing_interaction:
            log_status(f"Busy processing previous reply, queuing notice: {text}")
            return
        _is_processing_interaction = True

    def _interaction_thread():
        global _is_processing_interaction
        try:
            log_status(f"Processing incoming message from {sender}: '{text}'")
            if _gui_instance:
                _gui_instance.set_incoming_message(sender, text)
                _gui_instance.set_mic_status("Speaking incoming message...")

            # 1. Read ONLY her incoming message aloud
            if config.READ_INCOMING_ALOUD:
                tts_engine.speak(text, block=True)

            # 2. Activate microphone and listen for voice response
            if _gui_instance:
                _gui_instance.set_mic_status("🎙️ Listening... Speak your reply now!")

            reply_text = audio_engine.listen_and_transcribe(
                initial_timeout=9.0,
                status_callback=lambda s: _gui_instance.set_mic_status(s) if _gui_instance else None,
            )

            if not reply_text:
                log_status("No speech detected.")
                if _gui_instance:
                    _gui_instance.set_mic_status("Idle (No voice reply detected)")
                return

            log_status(f"Transcribed reply: '{reply_text}'")
            if _gui_instance:
                _gui_instance.set_transcribed_reply(reply_text)
                _gui_instance.set_mic_status("Voice transcribed!")

            # 3. Send message
            if config.AUTO_SEND and _gui_instance:
                log_status(f"Auto-send countdown ({config.AUTO_SEND_COUNTDOWN}s)...")
                _gui_instance.start_send_countdown(
                    config.AUTO_SEND_COUNTDOWN,
                    callback=_deliver_reply,
                )
            else:
                _deliver_reply(reply_text)

        except Exception as e:
            log_status(f"Interaction error: {e}")
        finally:
            with _interaction_lock:
                _is_processing_interaction = False

    threading.Thread(target=_interaction_thread, daemon=True).start()


def _deliver_reply(reply_text: str):
    """Sends the reply via WhatsApp in background thread."""
    if not _bot_instance:
        log_status("Error: WhatsApp bot not initialized.")
        return

    def _send_worker():
        log_status(f"Delivering reply: '{reply_text}'")
        if _gui_instance:
            _gui_instance.set_mic_status("Sending message to Keerthana...")

        success = _bot_instance.send_message(reply_text)
        if success:
            log_status("Message successfully delivered!")
            if _gui_instance:
                _gui_instance.set_mic_status("Reply sent! Idle.")
                _gui_instance.log(f"[SENT to {config.TARGET_CHAT}]: {reply_text}")
        else:
            log_status("Failed to send message.")
            if _gui_instance:
                _gui_instance.set_mic_status("Failed to send. Check WhatsApp window.")

    threading.Thread(target=_send_worker, daemon=True).start()


def trigger_manual_listen():
    """Triggered from the GUI 'Manual Voice Reply' button."""
    global _is_processing_interaction
    with _interaction_lock:
        if _is_processing_interaction:
            log_status("Microphone is currently busy.")
            return
        _is_processing_interaction = True

    try:
        log_status("Manual voice reply initiated...")
        if _gui_instance:
            _gui_instance.set_mic_status("🎙️ Listening for manual reply...")

        reply_text = audio_engine.listen_and_transcribe(
            initial_timeout=8.0,
            status_callback=lambda s: _gui_instance.set_mic_status(s) if _gui_instance else None,
        )

        if reply_text:
            if _gui_instance:
                _gui_instance.set_transcribed_reply(reply_text)
                _gui_instance.start_send_countdown(
                    config.AUTO_SEND_COUNTDOWN,
                    callback=_deliver_reply,
                )
        else:
            if _gui_instance:
                _gui_instance.set_mic_status("Idle (No voice reply detected)")
    finally:
        with _interaction_lock:
            _is_processing_interaction = False


def trigger_test_mic():
    """Records 3 seconds and verifies speech recognition."""
    log_status("Testing microphone (recording 3s)...")
    if _gui_instance:
        _gui_instance.set_mic_status("Testing mic (Say anything for 3s)...")
    
    tts_engine.speak("Say something for the microphone test.", block=True)
    text = audio_engine.record_fixed_duration(
        duration=3.5,
        status_callback=lambda s: _gui_instance.set_mic_status(s) if _gui_instance else None,
    )
    if text:
        log_status(f"Mic test success! Recognized: '{text}'")
        if _gui_instance:
            _gui_instance.set_mic_status("Mic test passed!")
            _gui_instance.set_transcribed_reply(f"[Test result]: {text}")
        tts_engine.speak(f"Microphone test heard: {text}", block=False)
    else:
        log_status("Mic test completed: No intelligible speech heard.")
        if _gui_instance:
            _gui_instance.set_mic_status("Mic test: No speech detected.")


def trigger_test_tts():
    """Verifies Text-To-Speech audio output."""
    log_status("Testing Text-to-Speech output...")
    tts_engine.speak("Hello Akarsh! Voice assistant audio system is functioning properly.", block=False)


def run_cli_mode():
    """Runs assistant purely in terminal without GUI."""
    global _bot_instance
    print("=" * 60)
    print(f"WhatsApp Voice Assistant (CLI Mode)")
    print(f"Target Chat: {config.TARGET_CHAT}")
    print("=" * 60)

    _bot_instance = WhatsAppBot(
        on_message=on_incoming_message,
        on_status=lambda s: print(f"[WhatsApp Status] {s}"),
    )
    _bot_instance.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping assistant...")
        _bot_instance.stop()


def main():
    parser = argparse.ArgumentParser(description="WhatsApp Voice Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode without desktop GUI")
    args = parser.parse_args()

    global _bot_instance, _gui_instance

    if args.cli:
        run_cli_mode()
        return

    # Start GUI mode
    _gui_instance = VoiceAssistantGUI(
        on_manual_listen=trigger_manual_listen,
        on_send_override=_deliver_reply,
        on_test_mic=trigger_test_mic,
        on_test_tts=trigger_test_tts,
    )

    _bot_instance = WhatsAppBot(
        on_message=on_incoming_message,
        on_status=handle_whatsapp_status,
    )
    _bot_instance.start()

    try:
        _gui_instance.log("Starting WhatsApp Voice Assistant...")
        _gui_instance.log(f"Target Chat: '{config.TARGET_CHAT}'")
        _gui_instance.run()
    finally:
        log_status("Shutting down WhatsApp Bot...")
        _bot_instance.stop()


if __name__ == "__main__":
    main()
