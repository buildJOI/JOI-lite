"""
Microphone helper. Records until you stop talking (not a fixed time), then
transcribes with Google's online recognizer. Uses sounddevice, so no PyAudio.
"""
import numpy as np
import sounddevice as sd
import speech_recognition as sr

RATE = 16000
BLOCK_SECONDS = 0.1
BLOCK = int(RATE * BLOCK_SECONDS)
END_SILENCE = 1.0      # seconds of quiet that end a sentence
MAX_UTTERANCE = 25.0   # longest single phrase
WAIT_FOR_SPEECH = 30.0 # listen this long for someone to start talking, then loop
_recognizer = sr.Recognizer()


def _rms(block):
    return float(np.sqrt(np.mean(np.square(block))))


def record_utterance():
    """Wait for speech, record until it ends. Returns float32 samples, or None if nobody spoke."""
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK) as stream:
        noise = [_rms(stream.read(BLOCK)[0]) for _ in range(5)]  # calibrate to the room
        threshold = min(0.15, max(0.008, float(np.median(noise)) * 3))

        frames, started, quiet, waited = [], False, 0.0, 0.0
        while True:
            block = stream.read(BLOCK)[0]
            level = _rms(block)
            if not started:
                waited += BLOCK_SECONDS
                if level > threshold:
                    started = True
                    frames.append(block)
                elif waited >= WAIT_FOR_SPEECH:
                    return None
                continue
            frames.append(block)
            quiet = quiet + BLOCK_SECONDS if level <= threshold else 0.0
            if quiet >= END_SILENCE or len(frames) * BLOCK_SECONDS >= MAX_UTTERANCE:
                break
    return np.concatenate(frames)


def transcribe(samples):
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    audio = sr.AudioData(pcm.tobytes(), RATE, 2)  # 16-bit mono
    try:
        return _recognizer.recognize_google(audio).strip() or None
    except sr.UnknownValueError:
        return None


def listen_text():
    """Listen for one phrase and return its text, or None if nothing was understood."""
    samples = record_utterance()
    if samples is None:
        return None
    return transcribe(samples)


def listen_once(seconds=6.0):
    """Compatibility helper: record one phrase (the length argument is ignored)."""
    return listen_text()
