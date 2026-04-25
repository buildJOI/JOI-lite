"""
JOI-lite — CLI mode
Run with: python app.py

Fix: asyncio.run() wraps the async chat loop so there's no
"coroutine was never awaited" or event-loop blocking issue.
"""
import asyncio
from config import DEFAULT_MOOD, ALL_MOODS
from model_handler import get_joi_response

BANNER = """
╔══════════════════════════════════════╗
║          J O I - l i t e            ║
║   Your AI companion — CLI edition   ║
╚══════════════════════════════════════╝
Type 'quit' to exit | 'mood <name>' to switch mood
Available moods: {moods}
"""


async def main():
    print(BANNER.format(moods=", ".join(ALL_MOODS)))

    mood = DEFAULT_MOOD
    history: list[dict] = []

    print(f"[Mood: {mood}] JOI is ready.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJOI: Goodbye. I'll be here whenever you need me. 💙")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("JOI: Goodbye. I'll be here whenever you need me. 💙")
            break

        # Mood switch command
        if user_input.lower().startswith("mood "):
            new_mood = user_input[5:].strip().lower()
            if new_mood in ALL_MOODS:
                mood = new_mood
                print(f"[Mood switched to: {mood}]\n")
            else:
                print(f"[Unknown mood '{new_mood}'. Options: {', '.join(ALL_MOODS)}]\n")
            continue

        reply = await get_joi_response(
            user_message=user_input,
            conversation_history=history,
            mood=mood,
        )

        print(f"\nJOI [{mood}]: {reply}\n")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

        # Keep last 40 messages
        if len(history) > 40:
            history = history[-40:]


if __name__ == "__main__":
    asyncio.run(main())