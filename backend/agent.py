"""
JOI agent: talks to Groq, runs tool calls, and handles permission replies.

Permission flow for sensitive actions:
  1. The model calls e.g. capture_camera.
  2. Nothing runs yet. JOI asks in plain words: "Mind if I use your camera? Yes or no?"
  3. The reply is understood naturally (yes, sure, go ahead, why not, no thanks...).
     Clear replies are matched locally; anything ambiguous goes to the model to classify.
  4. "Yes" allows that kind of action for the rest of the session, so it isn't asked
     again. "Just once" allows it one time. Power actions always ask.
"""
import json
import re
import threading
import uuid
from datetime import datetime

import httpx

from config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL, MOODS, DEFAULT_MOOD
from permissions import gate, NO_SESSION, CATEGORY_TEXT
from tools import execute_tool, openai_schemas

SESSIONS: dict[str, dict] = {}
MAX_HISTORY = 16

# ── Reply understanding ──────────────────────────────────────────────────────

_YES = re.compile(
    r"\b(yes|yeah|yep|yup|yess?|sure|ok|okay|alright|all right|go ahead|go for it|do it|"
    r"proceed|allow|approve|approved|fine|absolutely|certainly|definitely|of course|"
    r"why not|sounds good|please|confirm|affirmative|sure thing)\b")
_NO = re.compile(
    r"\b(no|nope|nah|don't|dont|do not|deny|denied|cancel|stop|never mind|nevermind|"
    r"not now|not really|negative|skip it|leave it)\b")
_ONCE = re.compile(r"\b(once|just this time|only this time|one time|this time)\b")
_ALWAYS = re.compile(r"\b(always|from now on|every time|whenever|keep allowing|for this session|session)\b")


def classify_reply(text: str) -> str | None:
    """Fast local check. Returns allow_session, allow, deny, or None when unsure."""
    t = text.lower().strip()
    if _NO.search(t) and not _YES.search(t):
        return "deny"
    if _YES.search(t) or _ALWAYS.search(t):
        return "allow" if _ONCE.search(t) else "allow_session"
    return None


_CLASSIFY_SYSTEM = (
    "A user was asked for permission to do something on their PC. Read their reply and answer with "
    "exactly one word: allow_session (they agreed, and it's fine to keep allowing this kind of thing), "
    "allow (they agreed, but only this one time), deny (they said no or changed their mind), "
    "or unclear (they moved on to something else or it's not a yes/no)."
)


# ── Persona ──────────────────────────────────────────────────────────────────

def _system(mood: str) -> str:
    persona = MOODS.get(mood, MOODS[DEFAULT_MOOD])
    now = datetime.now().strftime("%A, %B %d, %Y, %H:%M")
    return (
        f"{persona}\n\nCurrent date and time: {now}.\n"
        "Talk like a sharp, warm companion: natural short sentences, contractions, the occasional dry "
        "remark. Never sound like a manual or a call centre. Don't say 'as an AI'. Don't read out tool "
        "names or JSON. Don't open with filler like 'Certainly!' or 'Of course!'.\n\n"
        "You control this PC through tools, and you should use them instead of describing steps.\n"
        "- Anything about searching the web, YouTube or Wikipedia: use search_web, open_youtube or "
        "search_wikipedia with browser 'chrome'. 'Search X in Chrome' means search_web, not typing.\n"
        "- Only use type_text or press_keys when the user explicitly asks to type or press something, "
        "and pass window_title so the right window gets the keys. Never type into this chat.\n"
        "- Sensitive tools (camera, microphone, screenshots, USB, keyboard and mouse, shell, file changes, "
        "closing programs, power) ask the user first. Just call them; the app handles asking.\n"
        "- Never claim something happened unless a tool result says it did. If a tool fails, say so plainly "
        "and suggest what to try."
    )


# ── Model calls ──────────────────────────────────────────────────────────────

def _remember(session: dict, user_text: str, reply: str):
    session["history"].append({"role": "user", "content": user_text})
    session["history"].append({"role": "assistant", "content": reply})
    del session["history"][:-MAX_HISTORY]


async def _groq(messages: list[dict], use_tools: bool = True, max_tokens: int = 700) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
    payload = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    if use_tools:
        payload["tools"] = openai_schemas()
        payload["tool_choice"] = "auto"
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            f"{GROQ_BASE_URL}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
    if r.status_code >= 400:
        raise RuntimeError(f"Groq {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]


async def _classify(text: str, question: str) -> str:
    try:
        msg = await _groq(
            [{"role": "system", "content": _CLASSIFY_SYSTEM},
             {"role": "user", "content": f"Question: {question}\nReply: {text}"}],
            use_tools=False, max_tokens=5)
        word = (msg.get("content") or "").strip().lower().split()[0].strip(".,!")
        return word if word in ("allow_session", "allow", "deny") else "unclear"
    except Exception:
        return "unclear"


# ── Conversation ─────────────────────────────────────────────────────────────

async def _run_agent(session: dict, user_text: str, mood: str) -> str:
    base = [{"role": "system", "content": _system(mood)}] + session["history"][-MAX_HISTORY:]
    messages = base + [{"role": "user", "content": user_text}]
    try:
        for _ in range(6):
            msg = await _groq(messages, use_tools=True)
            calls = msg.get("tool_calls") or []
            if not calls:
                reply = (msg.get("content") or "").strip() or "Done."
                _remember(session, user_text, reply)
                return reply

            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await execute_tool(name, args)
                if result.get("status") == "permission_required":
                    session["pending"] = {
                        "tool": name,
                        "args": args,
                        "category": result["category"],
                        "description": result["message"],
                        "user_text": user_text,
                    }
                    what = CATEGORY_TEXT.get(result["category"], "do that")
                    reply = f"Mind if I {what}? Just say yes or no. A yes covers it for this session."
                    _remember(session, user_text, reply)
                    return reply
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(result, default=str)[:6000]})
        reply = "That's taking more steps than I can manage at once. Could you break it down?"
        _remember(session, user_text, reply)
        return reply
    except RuntimeError as e:
        if "400" in str(e):  # Groq rejected a malformed tool call: answer without tools
            try:
                msg = await _groq(base + [{"role": "user", "content": user_text}], use_tools=False)
                reply = (msg.get("content") or "").strip()
                _remember(session, user_text, reply)
                return reply
            except Exception:
                pass
        return f"Something went wrong: {e}"
    except httpx.HTTPError as e:
        return f"I can't reach my language model right now ({e.__class__.__name__}). Try again in a moment."


async def _finish_approved(session: dict, pending: dict, result: dict, mood: str) -> str:
    note = (f"The user said yes and I ran {pending['tool']} with {json.dumps(pending['args'], default=str)}. "
            f"Result: {json.dumps(result, default=str)[:4000]}. "
            "Tell the user what happened in one or two natural sentences. Don't call tools.")
    msgs = ([{"role": "system", "content": _system(mood)}] + session["history"][-MAX_HISTORY:]
            + [{"role": "user", "content": note}])
    try:
        msg = await _groq(msgs, use_tools=False)
        text = (msg.get("content") or "").strip() or result.get("message", "Done.")
    except Exception:
        text = result.get("message", "Done.")
    _remember(session, f"[approved] {pending['user_text']}", text)
    return text


async def decide(session_id: str, decision: str, mood: str = DEFAULT_MOOD) -> str:
    """Apply allow / allow_session / deny to the pending permission of a session."""
    session = SESSIONS.get(session_id)
    pending = session.get("pending") if session else None
    if not pending:
        return "Nothing is waiting for your answer."
    session["pending"] = None

    if decision == "deny":
        gate.audit({"event": "denied", "tool": pending["tool"], "category": pending["category"]})
        reply = "No problem, I've dropped that."
        _remember(session, f"[declined] {pending['user_text']}", reply)
        return reply

    scope = "once"
    if decision == "allow_session" and pending["category"] not in NO_SESSION:
        gate.grant_session(pending["category"])
        scope = "for this session"
    gate.audit({"event": "allowed", "tool": pending["tool"], "category": pending["category"], "scope": scope})

    result = await execute_tool(pending["tool"], pending["args"], approved=True)
    return await _finish_approved(session, pending, result, mood)


async def chat(message: str, session_id: str | None = None, mood: str = DEFAULT_MOOD) -> dict:
    sid = session_id or uuid.uuid4().hex
    session = SESSIONS.setdefault(sid, {"history": [], "pending": None})

    if session["pending"]:
        decision = classify_reply(message)
        if decision is None:
            decision = await _classify(message, session["pending"]["description"])
        if decision in ("allow", "allow_session", "deny"):
            return {"session_id": sid, "response": await decide(sid, decision, mood)}
        session["pending"] = None  # they moved on: treat this as a new request

    reply = await _run_agent(session, message, mood)
    return {"session_id": sid, "response": reply}


# ── Voice feed: spoken commands and replies, shown in the chat UI ─────────────
VOICE_FEED: list[dict] = []
_feed_seq = 0
_feed_lock = threading.Lock()


def add_voice_event(role: str, text: str):
    """Record a spoken command ("user") or JOI's reply ("assistant") for the UI."""
    global _feed_seq
    with _feed_lock:
        _feed_seq += 1
        VOICE_FEED.append({"id": _feed_seq, "role": role, "text": text})
        del VOICE_FEED[:-200]  # keep the last 200 entries
