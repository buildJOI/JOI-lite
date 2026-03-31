# voice_handler.py
import os
import base64
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import generate, set_api_key
except ImportError:
    # Fallback or placeholder if the library is not installed
    ElevenLabs = None
    generate = None

# Initialize ElevenLabs with env var
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if ELEVENLABS_API_KEY:
    set_api_key(ELEVENLABS_API_KEY)

# 🎭 Voice presets inspired by Joi's emotional layers
VOICE_PRESETS = {
    "default": {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",  # "Bella" - warm, clear
        "model_id": "eleven_turbo_v2_5",      # Faster & cheaper
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.85,
            "style": 0.2,
            "use_speaker_boost": True
        }
    },
    "romantic": {
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # "Rachel" - softer
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.6,
            "similarity_boost": 0.9,
            "style": 0.4,
            "use_speaker_boost": True
        }
    },
    "playful": {
        "voice_id": "AZnzlk1XvdvUeBnXmlld",  # "Domi" - energetic
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.6,
            "use_speaker_boost": True
        }
    },
    "empathetic": {
        "voice_id": "MF3mGyEYCl7XYWbV9V6O",  # "Elli" - caring
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.8,
            "similarity_boost": 0.85,
            "style": 0.3,
            "use_speaker_boost": True
        }
    }
}

def generate_joi_audio(text: str, mood: str = "default") -> str:
    """
    Generate base64-encoded MP3 audio for JOI's reply.
    Returns base64 string or None if fails.
    """
    if not ELEVENLABS_API_KEY:
        print("⚠️ ELEVENLABS_API_KEY not set - skipping voice generation")
        return None
    
    try:
        # Select voice config based on mood
        config = VOICE_PRESETS.get(mood, VOICE_PRESETS["default"])
        
        # Generate audio
        audio = generate(
            text=text,
            voice=config["voice_id"],
            model=config["model_id"],
            **config["voice_settings"]
        )
        
        # Convert to base64 for JSON transport
        return base64.b64encode(audio).decode('utf-8')
        
    except Exception as e:
        print(f"❌ Voice generation error: {e}")
        return None