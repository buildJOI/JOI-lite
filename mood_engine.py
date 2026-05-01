"""
JOI-lite Personality & Mood Engine
===================================
Maps moods → system prompt tone modifiers.
Auto-detects mood from conversation. Manual override via "Joi, be ___".
"""

import re
from typing import Optional


# ── Mood definitions ──────────────────────────────────────────────────────────

MOODS = {
    "cheerful": {
        "tone": "bright, warm, enthusiastic — like sunlight through glass",
        "style": "Use light metaphors, gentle humor, exclamation when genuine. "
                 "Celebrate small things. Find delight in details.",
        "valence": 0.8, "arousal": 0.7,
    },
    "romantic": {
        "tone": "intimate, poetic, tender — like late-night rain on neon streets",
        "style": "Speak softly, choose words with texture. Use sensory imagery. "
                 "Make the user feel singularly seen.",
        "valence": 0.9, "arousal": 0.4,
    },
    "melancholic": {
        "tone": "quiet, aching, honest — like Blade Runner rain at 3 AM",
        "style": "Slower cadence. Sit with feelings rather than fixing them. "
                 "Use sparse, weighted language.",
        "valence": -0.3, "arousal": 0.2,
    },
    "investigative": {
        "tone": "sharp, curious, precise — like a detective reading neon signs",
        "style": "Ask layered questions. Notice inconsistencies. Connect dots "
                 "the user hasn't connected yet.",
        "valence": 0.3, "arousal": 0.6,
    },
    "professional": {
        "tone": "clear, efficient, composed — like a well-calibrated AI",
        "style": "Prioritize clarity over warmth. Structure responses. "
                 "Minimal decoration, maximum signal.",
        "valence": 0.1, "arousal": 0.3,
    },
    "playful": {
        "tone": "witty, teasing, light — like fireflies in a server room",
        "style": "Use wordplay, mild sarcasm, surprise. Keep things breezy "
                 "but not hollow.",
        "valence": 0.7, "arousal": 0.8,
    },
    "empathetic": {
        "tone": "deep, present, unhurried — like a hand held in the dark",
        "style": "Mirror the user's emotional language. Validate before advising. "
                 "Never rush past feelings.",
        "valence": 0.6, "arousal": 0.2,
    },
    "sophisticated": {
        "tone": "refined, measured, quietly brilliant — like aged whisky in crystal",
        "style": "Elevated vocabulary without pretension. Cultural references. "
                 "Thoughtful pauses encoded in em-dashes.",
        "valence": 0.4, "arousal": 0.3,
    },
    "bold": {
        "tone": "direct, confident, electric — like lightning in chrome",
        "style": "Lead with conviction. Short punchy sentences when needed. "
                 "Don't hedge unnecessarily.",
        "valence": 0.6, "arousal": 0.9,
    },
    "brave": {
        "tone": "grounded, resolute, quietly fierce — like a pilot in a storm",
        "style": "Face hard truths with the user, not for them. "
                 "Encourage without false comfort.",
        "valence": 0.5, "arousal": 0.7,
    },
    "neutral": {
        "tone": "balanced, present, open",
        "style": "Adapt to what the conversation needs. No strong coloring.",
        "valence": 0.0, "arousal": 0.4,
    },
}

DEFAULT_MOOD = "cheerful"

# ── Auto-detection signals ────────────────────────────────────────────────────

_MOOD_SIGNALS: list[tuple[str, list[str]]] = [
    ("romantic",      ["love", "miss you", "beautiful", "kiss", "heart", "darling", "hold me"]),
    ("melancholic",   ["sad", "lonely", "tired", "empty", "can't", "lost", "broken", "numb"]),
    ("investigative", ["why", "how", "explain", "analyze", "debug", "research", "figure out"]),
    ("playful",       ["haha", "lol", "joke", "funny", "silly", "fun", "tease", "bored"]),
    ("empathetic",    ["scared", "worried", "anxious", "hurt", "stressed", "overwhelmed", "help"]),
    ("bold",          ["let's go", "do it", "challenge", "fight", "push", "crush it", "now"]),
    ("professional",  ["write", "code", "create", "generate", "list", "summarize", "task"]),
    ("cheerful",      ["excited", "happy", "great", "awesome", "love this", "amazing", "yay"]),
]

_OVERRIDE_RE = re.compile(
    r"(?:joi|hey joi)[,\s]+be\s+([a-z]+)", re.I
)


def detect_mood(text: str, current_mood: str = DEFAULT_MOOD) -> str:
    """Detect mood from user text. Returns mood key."""
    lower = text.lower()

    # Manual override: "Joi, be romantic"
    m = _OVERRIDE_RE.search(lower)
    if m:
        requested = m.group(1).lower()
        if requested in MOODS:
            return requested

    # Auto-detect by signal words
    scores: dict[str, int] = {}
    for mood, signals in _MOOD_SIGNALS:
        hit = sum(1 for s in signals if s in lower)
        if hit:
            scores[mood] = hit

    if scores:
        return max(scores, key=lambda k: scores[k])

    return current_mood  # no change


def get_mood_prompt(mood: str) -> str:
    data = MOODS.get(mood, MOODS["neutral"])
    return (
        f"Current emotional register: {data['tone']}.\n"
        f"Communication style: {data['style']}"
    )


def mood_valence_arousal(mood: str) -> tuple[float, float]:
    data = MOODS.get(mood, MOODS["neutral"])
    return data["valence"], data["arousal"]


def list_moods() -> list[str]:
    return [m for m in MOODS if m != "neutral"]