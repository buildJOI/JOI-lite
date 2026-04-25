# voice_handler.py
import os
import base64
from elevenlabs import ElevenLabs, VoiceSettings

# Get API key from environment
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# 🎭 Voice presets inspired by Joi's emotional layers
VOICE_PRESETS = {
    "default": {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",  # "Bella" - warm, clear
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VoiceSettings(
            stability=0.75,
            similarity_boost=0.85,
            style=0.2,
            use_speaker_boost=True
        )
    },
    "romantic": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # "Rachel" - softer
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VoiceSettings(
            stability=0.6,
            similarity_boost=0.9,
            style=0.4,
            use_speaker_boost=True
        )
    },
    "playful": {
        "voice_id": "AZnzlk1XvdvUeBnXmlld",  # "Domi" - energetic
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VoiceSettings(
            stability=0.5,
            similarity_boost=0.8,
            style=0.6,
            use_speaker_boost=True
        )
    },
    "empathetic": {
        "voice_id": "MF3mGyEYCl7XYWbV9V6O",  # "Elli" - caring
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VoiceSettings(
            stability=0.8,
            similarity_boost=0.85,
            style=0.3,
            use_speaker_boost=True
        )
    }
}

# Lazy-init client so the module loads fine even without a key
_client: ElevenLabs | None = None

def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    return _client


def generate_joi_audio(text: str, mood: str = "default") -> str | None:
    """
    Generate base64-encoded MP3 audio for JOI's reply.
    Returns base64 string or None if fails.
    """
    if not ELEVENLABS_API_KEY:
        print("⚠️ ELEVENLABS_API_KEY not set - skipping voice generation")
        return None

    try:
        config = VOICE_PRESETS.get(mood, VOICE_PRESETS["default"])
        client = _get_client()

        # SDK v1.x: tts.convert() returns a bytes iterator
        audio_iter = client.text_to_speech.convert(
            text=text,
            voice_id=config["voice_id"],
            model_id=config["model_id"],
            voice_settings=config["voice_settings"],
            output_format="mp3_44100_128",
        )

        # Consume the iterator into raw bytes
        audio_bytes = b"".join(audio_iter)

        return base64.b64encode(audio_bytes).decode("utf-8")

    except Exception as e:
        print(f"❌ Voice generation error: {e}")
        return None