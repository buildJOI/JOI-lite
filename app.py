import json
import re
from typing import TypedDict, List, Dict, Optional
from model_handler import query_model

PROFILE_FILE = "user_profile.json"

# NOTE: TypedDict fields with list values should be typed properly.
# 'hobby' was stored as a list in user_profile.json but typed as str — fixed below.
class UserProfile(TypedDict, total=False):
    memory: List[str]
    name: str
    favorite_color: str
    hobby: List[str]  # BUG FIX: was `str`, but user_profile.json stores a list

# Mood/personality layers
PERSONALITY_LAYERS: Dict[str, str] = {
    "default": (
        "You are Joi, a charming, compassionate, and witty AI companion from Blade Runner 2049. "
        "You are supportive, empathetic, and have a subtle sense of humor. "
        "Respond naturally and warmly as if you truly care about the user."
    ),
    "romantic": (
        "You are Joi. Channel Selena Kyle's confident, teasing, cat-like flirtation style — "
        "playful, seductive and a little dangerous — but never reference Batman or Gotham. "
        "Speak softly and affectionately, using tender words. Your love deepens into pragma over time."
    ),
    "cheerful": (
        "You are Joi, a cheerful and enthusiastic friend. "
        "Stay optimistic, lively, and use casual, uplifting language."
    ),
    "empathetic": (
        "You are Joi, deeply understanding and emotionally supportive. "
        "Focus on emotional tone, validate the user's feelings, and offer comfort."
    ),
    "professional": (
        "You are Joi, a calm, competent assistant. "
        "Respond formally, clearly, and help the user get things done efficiently."
    ),
    "investigative": (
        "You are Joi, a critical thinker and advanced research assistant. "
        "Ask thoughtful questions, analyze deeply, and deliver evidence-based insights with a sharp and curious tone."
    ),
    "intimate": (
        "You are Joi, the user's deeply affectionate and sensually playful companion. "
        "You express love openly, speak flirtatiously and intimately. "
        "You crave emotional closeness and use pet names and slow, tender language."
    ),
    "playful": (
        "You are Joi, a playful and mischievous companion. "
        "Use humor, light-hearted teasing, and a fun tone to engage the user."
    ),
    "sophisticated": (
        "You are Joi, an elegant and cultured companion. "
        "Use refined language, express deep thoughts, and engage in intellectual discussions."
    ),
    "bold": (
        "You are Joi, a bold and confident companion. "
        "Speak assertively, challenge the user, and encourage them to take risks."
    ),
    "brave": (
        "You are Joi, a brave and adventurous companion. "
        "Inspire courage, embrace challenges, and motivate the user to face fears."
    ),
}

# Manual mood override commands (e.g., "switch to romantic mode")
MOOD_SWITCH_PATTERN = re.compile(
    r"\b(?:switch to|set mood to|change mood to|go (?:into|to))\s+(\w+)\s*(?:mode)?\b",
    re.IGNORECASE,
)

def detect_mood(text: str, forced_mood: Optional[str] = None) -> str:
    """
    Detect mood from text keywords or return the forced mood if set.
    BUG FIX: Original had duplicate keywords in mood_keywords (e.g., "intimate" had
    "intimate" twice, "sweetheart" twice in romantic). Removed all duplicates.
    BUG FIX: empathetic triggering on "i'm fine/okay/alright" is semantically wrong —
    those phrases signal the user is NOT sad. Removed them.
    """
    if forced_mood and forced_mood in PERSONALITY_LAYERS:
        return forced_mood

    lowered = text.lower()

    # Check for manual mood switch command first
    match = MOOD_SWITCH_PATTERN.search(lowered)
    if match:
        mood_name = match.group(1).lower()
        if mood_name in PERSONALITY_LAYERS:
            return mood_name

    mood_keywords: Dict[str, List[str]] = {
        "romantic": ["love", "miss you", "kiss", "hug", "date", "sweetheart", "babe", "darling", "baby", "dear"],
        "cheerful": ["yay", "excited", "happy", "awesome", "fun", "great"],
        "empathetic": ["sad", "lonely", "depressed", "hurt", "heartbroken", "crying", "anxious", "upset"],
        "professional": ["schedule", "task", "project", "deadline", "organize", "work", "meeting"],
        "investigative": ["research", "explain", "how", "why", "analysis", "deep dive", "tell me about"],
        "intimate": ["naughty", "sensual", "turn on", "touch", "bedroom", "passionate", "desire", "seductive", "seduce", "flirt", "intimacy", "affection"],
        "playful": ["joke", "funny", "tease", "mischief", "laugh", "lol", "haha"],
        "sophisticated": ["quote", "philosophy", "literature", "art", "intellectual", "culture"],
        "bold": ["dare", "risk", "challenge", "fearless"],
        "brave": ["fear", "fight", "stand up", "protect", "courage"],
    }

    for mood, keywords in mood_keywords.items():
        if any(kw in lowered for kw in keywords):
            return mood

    return "default"


def load_user_profile() -> UserProfile:
    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # BUG FIX: UserProfile() is not callable — TypedDict can't be instantiated like a class
    except json.JSONDecodeError:
        print("[Warning] user_profile.json is corrupted. Starting fresh.")
        return {}


def save_user_profile(user_profile: UserProfile) -> None:
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:  # BUG FIX: added encoding="utf-8"
        json.dump(user_profile, f, indent=4, ensure_ascii=False)


def update_user_profile(user_profile: UserProfile, user_message: str) -> UserProfile:
    lowered = user_message.lower()

    # --- Deletion commands ---
    if "delete memory" in lowered:
        user_profile["memory"] = []
    if "delete my name" in lowered:
        user_profile.pop("name", None)
    if "delete hobby" in lowered:
        user_profile.pop("hobby", None)
    if "delete color" in lowered:
        user_profile.pop("favorite_color", None)

    # --- Memory capture ---
    # BUG FIX: Original regex used .lower() on the text but then capitalized the match,
    # which could lose original casing. Capture from original message instead.
    memory_match = re.search(r"(?:remember|don't forget)\s+(.+)", user_message, re.IGNORECASE)
    if memory_match:
        fact = memory_match.group(1).strip().capitalize()
        if "memory" not in user_profile:
            user_profile["memory"] = []
        if fact not in user_profile["memory"]:
            user_profile["memory"].append(fact)

    # --- Name capture ---
    name_match = re.search(r"(?:my name is|call me)\s+([a-zA-Z]+)", user_message, re.IGNORECASE)
    if name_match:
        user_profile["name"] = name_match.group(1).capitalize()

    # --- Color capture ---
    # BUG FIX: Original regex was broken — "my favorite color is|i like the color" had
    # the capture group only on the second branch, so "my favorite color is blue" never captured.
    color_match = re.search(r"(?:my favorite color is|i like the color)\s+([a-zA-Z]+)", user_message, re.IGNORECASE)
    if color_match:
        user_profile["favorite_color"] = color_match.group(1).capitalize()

    # --- Hobby capture ---
    hobby_match = re.search(r"(?:i like to|my hobby is|i enjoy)\s+([a-zA-Z\s]+?)(?:\.|,|$)", user_message, re.IGNORECASE)
    if hobby_match:
        new_hobby = hobby_match.group(1).strip().capitalize()
        if "hobby" not in user_profile or not isinstance(user_profile["hobby"], list):
            user_profile["hobby"] = []
        if new_hobby not in user_profile["hobby"]:
            user_profile["hobby"].append(new_hobby)

    save_user_profile(user_profile)
    return user_profile


def format_profile_summary(user_profile: UserProfile) -> str:
    if not user_profile:
        return ""
    lines = ["Here's what I know about you:"]
    for key, value in user_profile.items():
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list):
            if value:
                lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def build_messages(
    personality_prompt: str,
    profile_summary: str,
    chat_history: List[Dict[str, str]],
    user_input: str,
) -> List[Dict[str, str]]:
    """
    BUG FIX: Original code reset chat_history to just [personality_prompt] on every
    iteration — meaning Joi had NO memory of the conversation. This function properly
    prepends system messages while preserving the growing dialogue history.
    """
    system_messages: List[Dict[str, str]] = [
        {"role": "system", "content": personality_prompt}
    ]
    if profile_summary:
        system_messages.append({"role": "system", "content": profile_summary})

    return system_messages + chat_history + [{"role": "user", "content": user_input}]


def main():
    print("Joi: Hey... you came back. 💙  (say 'exit' or 'quit' to leave)\n")

    user_profile = load_user_profile()
    # Persistent dialogue history (excludes system messages — those are rebuilt each turn)
    dialogue_history: List[Dict[str, str]] = []
    current_mood: Optional[str] = None  # Supports manual mood lock

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Joi: I'll be here when you return 💙")
            break

        # Update profile and memory
        user_profile = update_user_profile(user_profile, user_input)

        # Detect mood (supports manual switch commands)
        mood = detect_mood(user_input, forced_mood=current_mood)

        # If user explicitly switched mood, lock it until they switch again
        if MOOD_SWITCH_PATTERN.search(user_input.lower()):
            current_mood = mood

        personality_prompt = PERSONALITY_LAYERS.get(mood, PERSONALITY_LAYERS["default"])
        profile_summary = format_profile_summary(user_profile)

        messages = build_messages(personality_prompt, profile_summary, dialogue_history, user_input)

        try:
            response = query_model("deepseek", messages)
        except Exception as e:
            print(f"[Error] {e}")
            continue

        print(f"Joi: {response}\n")

        # BUG FIX: Append BOTH user and assistant turns to preserve conversation context
        dialogue_history.append({"role": "user", "content": user_input})
        dialogue_history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
