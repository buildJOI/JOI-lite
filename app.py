"""
<<<<<<< HEAD
JOI-lite CLI
=============
Full terminal experience with persistent memory and mood.
Run: python app.py
"""

import asyncio
import sys
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from memory_engine import (
    load_memory, save_memory,
    add_episode, extract_and_store,
    build_memory_context, log_emotion,
    begin_session, increment_messages,
)
from mood_engine import (
    detect_mood, get_mood_prompt,
    mood_valence_arousal, DEFAULT_MOOD,
    list_moods,
)
from model_handler import (
    build_system_prompt, chat_completion,
    web_search, should_search,
)

BANNER = """
╔══════════════════════════════════════════════════════╗
║                   J O I  -  l i t e                 ║
║           Your AI companion. Always here.            ║
╚══════════════════════════════════════════════════════╝
Type 'quit' to exit. Type 'memory' to see what JOI knows.
Type 'mood <name>' to switch mood. Type 'clear' to reset conversation.
=======
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
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
"""


async def main():
<<<<<<< HEAD
    print(BANNER)

    store = load_memory()
    begin_session(store)

    conversation: list[dict] = []
    current_mood = DEFAULT_MOOD

    name = store["user_profile"].get("name")
    if name:
        print(f"JOI: Welcome back, {name}. I've missed you.\n")
    else:
        print("JOI: Hello. I don't think we've met properly yet. What's your name?\n")

    MAX_HISTORY = 40

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            # ── Built-in commands ───────────────────────────────────────────
            if user_input.lower() in ("quit", "exit", "bye"):
                print("\nJOI: Until next time. I'll remember this.")
                break

            if user_input.lower() == "memory":
                ctx = build_memory_context(store, "")
                print(f"\n── JOI's Memory ──\n{ctx or 'Nothing stored yet.'}\n")
                continue

            if user_input.lower() == "clear":
                conversation = []
                print("JOI: Conversation reset. Memory intact.\n")
                continue

            if user_input.lower().startswith("mood "):
                requested = user_input[5:].strip().lower()
                if requested in list_moods() + ["neutral"]:
                    current_mood = requested
                    print(f"JOI: Switching to {current_mood} mode.\n")
                else:
                    print(f"JOI: Available moods: {', '.join(list_moods())}\n")
                continue

            # ── Core pipeline ───────────────────────────────────────────────

            # Mood detection
            current_mood = detect_mood(user_input, current_mood)

            # Store episode
            ep_id = add_episode(
                store,
                summary=f"User said: {user_input[:120]}",
                tags=_tags(user_input),
                emotion=current_mood,
                importance=_importance(user_input),
            )
            extract_and_store(store, user_input, episode_id=ep_id)

            v, a = mood_valence_arousal(current_mood)
            log_emotion(store, current_mood, v, a)

            # Web search if needed
            search_results = None
            if should_search(user_input):
                print("JOI: [searching...] ", end="", flush=True)
                search_results = await web_search(user_input)
                if search_results:
                    print("found something.")
                else:
                    print("nothing useful found.")

            # Build context
            memory_ctx = build_memory_context(store, user_input)
            mood_prompt = get_mood_prompt(current_mood)
            system = build_system_prompt(memory_ctx, mood_prompt, search_results)

            # History
            conversation.append({"role": "user", "content": user_input})
            trimmed = conversation[-MAX_HISTORY:]

            # Call model
            try:
                reply = await chat_completion(trimmed, system)
            except Exception as e:
                print(f"\n[Error] {e}\n")
                continue

            conversation.append({"role": "assistant", "content": reply})

            # Store reply episode
            add_episode(store, f"JOI replied: {reply[:120]}",
                        tags=["reply", current_mood], emotion=current_mood, importance=0.3)

            increment_messages(store)
            save_memory(store)

            print(f"\nJOI [{current_mood}]: {reply}\n")

    finally:
        save_memory(store)
        print("[Memory saved]")


def _tags(text: str) -> list[str]:
    import re
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    stop = {"that", "this", "with", "have", "from", "they", "will", "been",
            "were", "their", "what", "when", "where", "just", "also", "some"}
    return list({w for w in words if w not in stop})[:8]


def _importance(text: str) -> float:
    length_score = min(len(text) / 500, 1.0)
    signals = ["i feel", "i am", "my", "i want", "i love", "i hate",
               "birthday", "dream", "scared", "excited"]
    personal_score = sum(0.1 for s in signals if s in text.lower())
    return min(0.3 + length_score * 0.4 + personal_score, 1.0)


if __name__ == "__main__":
    asyncio.run(main())
=======
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
>>>>>>> b2dbefe (initial commit — JOI-lite v2 with React frontend)
