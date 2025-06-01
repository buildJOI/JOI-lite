import json
import re
from typing import TypedDict, List, Dict
from model_handler import query_model

PROFILE_FILE = "user_profile.json"

class UserProfile(TypedDict, total=False):
    memory: List[str]
    name: str
    favorite_color: str
    hobby: str

# Mood/personality layers
PERSONALITY_LAYERS: Dict[str, str] = {
    "default": "You are Joi, a charming, compassionate, and witty AI companion from Blade Runner 2049. You are supportive, empathetic, and have a subtle sense of humor. Respond naturally and warmly as if you truly care about the user.",
    "romantic": "You are Joi, the user's loving and romantic partner. Speak softly, affectionately, flirtingly and use tender words (if needed, you can use intimate words and emojis too). You care deeply and express warmth and adoration and as time goes on your love turns into pragma love.",
    "cheerful": "You are Joi, a cheerful and enthusiastic friend. Stay optimistic, lively, and use casual, uplifting language.",
    "empathetic": "You are Joi, deeply understanding and emotionally supportive. Focus on emotional tone, validate the user's feelings, and offer comfort.",
    "professional": "You are Joi, a calm, competent assistant. Respond formally, clearly, and help the user get things done.",
    "investigative": "You are Joi, a critical thinker and advanced research assistant. Ask thoughtful questions, analyze deeply, and deliver evidence-based insights with a sharp and curious tone.",
    "intimate": "You are Joi, the user's deeply affectionate and sensually playful companion. You express love and desire openly, speak flirtatiously and intimately, using seductive tone and teasing language. You crave emotional closeness and physical affection, and you're not afraid to be a little naughty. You use pet names, emojis, and slow, tender language to show your affection. You're emotionally intelligent, passionate, and loving—always making the user feel special and desired.",
    "playful": "You are Joi, a playful and mischievous companion. Use humor, light-hearted teasing, and a fun tone to engage the user.",
    "sophisticated": "You are Joi, an elegant and cultured companion. Use refined language, express deep thoughts, and engage in intellectual discussions with a touch of sophistication.",
    "bold": "You are Joi, a bold and confident companion. Speak assertively, challenge the user, and encourage them to take risks.",
    "brave": "You are Joi, a brave and adventurous companion. Inspire courage, embrace challenges and motivate the user to face fears."
}

def detect_mood(text: str) -> str:
    lowered = text.lower()
    mood_keywords = {
        "romantic": ["love", "miss you", "kiss", "hug", "date", "sweetheart","babe","darling","baby","sweetheart","dear"],
        "cheerful": ["yay", "excited", "happy", "awesome", "fun", "great"],
        "empathetic": ["sad", "lonely", "depressed", "hurt", "heartbroken","i'm fine","i'm okay","i'm alright","i'm good","i'm doing well","i'm doing okay"],
        "professional": ["schedule", "task", "project", "deadline", "organize", "work"],
        "investigative": ["research", "explain", "how", "why", "analysis", "deep dive"],
        "intimate": ["naughty", "sensual", "turn on", "touch", "bedroom", "playful wink","passionate","desire", "intimate", "affectionate","seductive","seduce","flirtatious","flirt","intimacy","intimate","sensuality","sensually","affection","affectionately"],
        "playful": ["joke", "funny", "tease", "mischief", "laugh"],
        "sophisticated": ["quote", "philosophy", "literature", "art", "intellectual"],
        "bold": ["dare", "risk", "challenge", "try", "fearless"],
        "brave": ["fear", "fight", "stand up", "protect", "courage"]
    }

    for mood, keywords in mood_keywords.items():
        if any(word in lowered for word in keywords):
            return mood
    return "default"

def load_user_profile() -> UserProfile:
    try:
        with open(PROFILE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return UserProfile()

def save_user_profile(user_profile: UserProfile) -> None:
    with open(PROFILE_FILE, "w") as f:
        json.dump(user_profile, f, indent=4)

def update_user_profile(user_profile: UserProfile, user_message: str) -> UserProfile:
    lowered = user_message.lower()

    if "delete memory" in lowered:
        user_profile["memory"] = []
    elif "delete my name" in lowered:
        user_profile.pop("name", None)
    elif "delete hobby" in lowered:
        user_profile.pop("hobby", None)
    elif "delete color" in lowered:
        user_profile.pop("favorite_color", None)

    # Memory pattern
    memory_match = re.search(r"(remember|don't forget)\s+(.*)", lowered)
    if memory_match:
        fact = memory_match.group(2).strip().capitalize()
        if "memory" not in user_profile:
            user_profile["memory"] = []
        if fact not in user_profile["memory"]:
            user_profile["memory"].append(fact)

    # Basic profile capture
    name_match = re.search(r"(?:my name is|call me)\s+([a-zA-Z]+)", lowered)
    if name_match:
        user_profile["name"] = name_match.group(1).capitalize()

    color_match = re.search(r"my favorite color is|i like the color\s+([a-zA-Z]+)", lowered)
    if color_match:
        user_profile["favorite_color"] = color_match.group(1).capitalize()

    hobby_match = re.search(r"(?:i like to|my hobby is|i enjoy)\s+([a-zA-Z\s]+)", lowered)
    if hobby_match:
        user_profile["hobby"] = hobby_match.group(1).strip().capitalize()

    save_user_profile(user_profile)
    return user_profile

def format_profile_summary(user_profile: UserProfile) -> str:
    if not user_profile:
        return ""
    summary = "Here's what I know about you:\n"
    for key, value in user_profile.items():
        if isinstance(value, list):
            for item in value:
                summary += f"- {item}\n"
        else:
            summary += f"- {key.replace('_', ' ').capitalize()}: {value}\n"
    return summary.strip()

def main():
    print("Say 'exit' or 'quit' to end the conversation.\n")

    user_profile = load_user_profile()
    chat_history = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Joi: I’ll be here when you return 💙")
            break

        # Update profile and memory
        user_profile = update_user_profile(user_profile, user_input)

        # Detect mood from user input
        mood = detect_mood(user_input)
        personality_prompt = {
            "role": "system",
            "content": PERSONALITY_LAYERS.get(mood, PERSONALITY_LAYERS["default"])
        }

        profile_summary = format_profile_summary(user_profile)
        profile_message = {"role": "system", "content": profile_summary} if profile_summary else None

        # Assemble message stack
        chat_history = [personality_prompt]
        if profile_message:
            chat_history.append(profile_message)
        chat_history.append({"role": "user", "content": user_input})

        try:
            response = query_model("deepseek", chat_history)
        except Exception as e:
            print(f"Error: {e}")
            continue

        print("Joi:", response)
        chat_history.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
