"""
Audio Engine: Captures microphone input with silence detection and transcribes via SpeechRecognition.
Uses sounddevice (native WASAPI/MME on Windows 11) to avoid PyAudio binary installation hurdles.
"""
import time
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import config

_recognizer = sr.Recognizer()


def _calculate_rms(audio_chunk: np.ndarray) -> float:
    """Calculates root-mean-square amplitude of an audio block."""
    if len(audio_chunk) == 0:
        return 0.0
    # audio_chunk is int16, convert to float to prevent overflow
    return float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))


def calibrate_ambient_noise(duration: float = 1.0) -> float:
    """Records ambient noise for `duration` seconds and estimates baseline energy."""
    try:
        samples = int(duration * config.SAMPLE_RATE)
        recording = sd.rec(
            samples,
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="int16",
            blocking=True,
        )
        ambient_rms = _calculate_rms(recording)
        # Set dynamic threshold slightly above ambient noise
        dynamic_threshold = max(config.ENERGY_THRESHOLD, ambient_rms * 1.5)
        return dynamic_threshold
    except Exception as e:
        print(f"[Audio] Ambient calibration notice: {e}")
        return config.ENERGY_THRESHOLD


def listen_and_transcribe(
    initial_timeout: float = 8.0,
    silence_limit: float = config.SILENCE_TIMEOUT_SECONDS,
    max_duration: float = config.RECORD_MAX_SECONDS,
    status_callback=None,
) -> str | None:
    """
    Listens for speech through the microphone.
    Automatically starts recording when speech is detected,
    and stops when silence is detected for `silence_limit` seconds.

    Returns the transcribed text, or None if no speech was detected.
    """
    chunk_duration = 0.1  # 100ms chunks
    chunk_samples = int(chunk_duration * config.SAMPLE_RATE)

    if status_callback:
        status_callback("Calibrating microphone...")
    threshold = calibrate_ambient_noise(0.6)

    if status_callback:
        status_callback(f"Listening... (Threshold: {int(threshold)})")
    else:
        print(f"[Audio] Listening... Speak now (Energy Threshold: {int(threshold)})")

    collected_chunks = []
    has_speech_started = False
    speech_start_time = None
    silence_start_time = None
    overall_start_time = time.time()

    try:
        with sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="int16",
            blocksize=chunk_samples,
        ) as stream:
            while True:
                # Read 100ms chunk
                chunk, overflowed = stream.read(chunk_samples)
                rms = _calculate_rms(chunk)
                now = time.time()

                if not has_speech_started:
                    # Check if user began speaking
                    if rms > threshold:
                        has_speech_started = True
                        speech_start_time = now
                        silence_start_time = None
                        collected_chunks.append(chunk)
                        if status_callback:
                            status_callback("Recording your reply...")
                        else:
                            print("[Audio] Speech detected, recording reply...")
                    elif (now - overall_start_time) > initial_timeout:
                        # Timed out waiting for user to start speaking
                        if status_callback:
                            status_callback("No speech detected (timeout).")
                        else:
                            print("[Audio] No speech detected within initial timeout.")
                        return None
                else:
                    # Already speaking, collect chunk
                    collected_chunks.append(chunk)

                    # Check for silence or max duration
                    if rms < threshold:
                        if silence_start_time is None:
                            silence_start_time = now
                        elif (now - silence_start_time) >= silence_limit:
                            # Finished speaking!
                            if status_callback:
                                status_callback("Processing speech...")
                            else:
                                print("[Audio] Finished speaking, transcribing...")
                            break
                    else:
                        # User is still speaking, reset silence timer
                        silence_start_time = None

                    # Check max duration cap
                    if (now - speech_start_time) >= max_duration:
                        if status_callback:
                            status_callback("Reached maximum duration cap.")
                        break

    except Exception as e:
        print(f"[Audio Stream Error] {e}")
        if status_callback:
            status_callback(f"Mic error: {e}")
        return None

    if not collected_chunks:
        return None

    # Concatenate all recorded chunks into single PCM buffer
    full_audio = np.concatenate(collected_chunks, axis=0)
    audio_bytes = full_audio.tobytes()

    return transcribe_audio_bytes(audio_bytes, status_callback=status_callback)


def transcribe_audio_bytes(audio_bytes: bytes, status_callback=None) -> str | None:
    """Converts raw 16-bit PCM bytes to text using SpeechRecognition."""
    try:
        audio_data = sr.AudioData(audio_bytes, config.SAMPLE_RATE, 2)
        if status_callback:
            status_callback("Transcribing audio...")

        # Primary transcription: en-IN (optimized for Indian English)
        try:
            transcript = _recognizer.recognize_google(
                audio_data, language=config.STT_LANGUAGE
            )
        except sr.UnknownValueError:
            # Secondary retry with standard English
            transcript = _recognizer.recognize_google(
                audio_data, language="en-US"
            )

        transcript = transcript.strip()
        print(f"[Audio Transcribed] -> '{transcript}'")
        return transcript

    except sr.UnknownValueError:
        print("[Audio] Could not understand audio.")
        if status_callback:
            status_callback("Could not understand audio.")
        return None
    except sr.RequestError as e:
        print(f"[Audio] STT service request error: {e}")
        if status_callback:
            status_callback(f"STT Service Error: {e}")
        return None
    except Exception as e:
        print(f"[Audio] Unexpected STT error: {e}")
        return None


def record_fixed_duration(duration: float = 3.0, status_callback=None) -> str | None:
    """Records for a fixed duration (useful for quick microphone test)."""
    if status_callback:
        status_callback(f"Recording {duration}s test audio...")
    print(f"[Audio] Recording for {duration} seconds...")

    samples = int(duration * config.SAMPLE_RATE)
    recording = sd.rec(
        samples,
        samplerate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        dtype="int16",
        blocking=True,
    )
    return transcribe_audio_bytes(recording.tobytes(), status_callback=status_callback)


if __name__ == "__main__":
    print("[Audio Engine Test] Speak a test phrase into your mic now...")
    res = listen_and_transcribe(initial_timeout=6.0)
    print(f"[Result] Recognized: {res}")
