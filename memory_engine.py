"""
JOI-lite Memory Engine
======================
JARVIS/JOI-grade memory: episodic, semantic, emotional, and procedural.
No vector DB needed — pure JSON + TF-IDF retrieval for zero-dependency deploy.
"""

import json
import os
import math
import re
import time
from datetime import datetime
from collections import defaultdict
from typing import Optional


MEMORY_FILE = "memory_store.json"


# ── Schema ────────────────────────────────────────────────────────────────────

def _blank_store() -> dict:
    return {
        "version": 2,
        "user_profile": {
            "name": None,
            "preferred_name": None,
            "traits": [],          # ["curious", "night owl", …]
            "interests": [],
            "dislikes": [],
            "goals": [],
            "birthday": None,
            "timezone": None,
            "language_style": "casual",  # casual / formal / playful
        },
        "episodic": [],            # list of {id, timestamp, summary, tags, emotion, importance}
        "semantic": {},            # {concept: {value, confidence, last_updated, source_episode}}
        "emotional_arc": [],       # list of {timestamp, valence, arousal, label} — mood over time
        "relationships": {},       # {entity: {type, description, sentiment}}
        "procedural": {},          # {task_type: preferred_approach}
        "stats": {
            "total_messages": 0,
            "sessions": 0,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migrate v1 → v2
            if data.get("version", 1) < 2:
                data = _migrate_v1(data)
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return _blank_store()


def save_memory(store: dict):
    store["stats"]["last_seen"] = datetime.now().isoformat()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def _migrate_v1(old: dict) -> dict:
    """Upgrade old user_profile.json format into v2 store."""
    store = _blank_store()
    op = old.get("user_profile", old)
    store["user_profile"]["name"] = op.get("name") or op.get("user_name")
    store["user_profile"]["traits"] = op.get("personality_traits", [])
    store["user_profile"]["interests"] = op.get("interests", [])
    # Carry over any old semantic facts
    for k, v in op.items():
        if k not in ("name", "personality_traits", "interests"):
            store["semantic"][k] = {"value": v, "confidence": 0.8,
                                    "last_updated": datetime.now().isoformat(),
                                    "source_episode": "migration"}
    store["version"] = 2
    return store


# ── Episodic memory ───────────────────────────────────────────────────────────

def add_episode(store: dict, summary: str, tags: list[str],
                emotion: str = "neutral", importance: float = 0.5) -> str:
    ep_id = f"ep_{int(time.time()*1000)}"
    episode = {
        "id": ep_id,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "tags": tags,
        "emotion": emotion,
        "importance": importance,
    }
    store["episodic"].append(episode)
    # Keep only top-600 by importance (JARVIS doesn't forget, but we're lean)
    if len(store["episodic"]) > 600:
        store["episodic"].sort(key=lambda e: e["importance"], reverse=True)
        store["episodic"] = store["episodic"][:500]
    return ep_id


# ── Semantic memory ───────────────────────────────────────────────────────────

def set_fact(store: dict, concept: str, value, confidence: float = 0.9,
             source_episode: Optional[str] = None):
    store["semantic"][concept] = {
        "value": value,
        "confidence": confidence,
        "last_updated": datetime.now().isoformat(),
        "source_episode": source_episode,
    }


def get_fact(store: dict, concept: str):
    entry = store["semantic"].get(concept)
    return entry["value"] if entry else None


# ── TF-IDF retrieval ──────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    counts: dict[str, int] = defaultdict(int)
    for t in tokens:
        counts[t] += 1
    total = max(len(tokens), 1)
    return {t: c / total for t, c in counts.items()}


def retrieve_relevant_episodes(store: dict, query: str, top_k: int = 5) -> list[dict]:
    """Return the most semantically relevant episodes to `query`."""
    episodes = store["episodic"]
    if not episodes:
        return []

    q_tokens = _tokenize(query)
    q_tf = _tf(q_tokens)

    # Build IDF from corpus
    df: dict[str, int] = defaultdict(int)
    for ep in episodes:
        for word in set(_tokenize(ep["summary"] + " " + " ".join(ep["tags"]))):
            df[word] += 1
    N = len(episodes)

    def score(ep: dict) -> float:
        doc = ep["summary"] + " " + " ".join(ep["tags"])
        d_tokens = _tokenize(doc)
        d_tf = _tf(d_tokens)
        tfidf_score = 0.0
        for word, qtf in q_tf.items():
            if word in d_tf:
                idf = math.log((N + 1) / (df[word] + 1)) + 1
                tfidf_score += qtf * d_tf[word] * idf
        # Boost by importance and recency
        recency = 1.0 / (1.0 + _days_ago(ep["timestamp"]) * 0.05)
        return tfidf_score * (0.7 + 0.3 * ep["importance"]) * recency

    ranked = sorted(episodes, key=score, reverse=True)
    return ranked[:top_k]


def _days_ago(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso)
        return (datetime.now() - dt).total_seconds() / 86400
    except Exception:
        return 0.0


# ── Emotional arc ─────────────────────────────────────────────────────────────

def log_emotion(store: dict, label: str, valence: float, arousal: float):
    """valence: -1 (negative) → +1 (positive), arousal: 0 (calm) → 1 (intense)"""
    store["emotional_arc"].append({
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "valence": valence,
        "arousal": arousal,
    })
    if len(store["emotional_arc"]) > 200:
        store["emotional_arc"] = store["emotional_arc"][-200:]


def current_mood_summary(store: dict) -> str:
    arc = store["emotional_arc"]
    if not arc:
        return "neutral"
    recent = arc[-5:]
    avg_valence = sum(e["valence"] for e in recent) / len(recent)
    avg_arousal = sum(e["arousal"] for e in recent) / len(recent)
    if avg_valence > 0.4 and avg_arousal > 0.5:
        return "excited and happy"
    if avg_valence > 0.4:
        return "warm and content"
    if avg_valence < -0.4 and avg_arousal > 0.5:
        return "tense or distressed"
    if avg_valence < -0.4:
        return "low or melancholic"
    return "neutral and steady"


# ── Entity / relationship ─────────────────────────────────────────────────────

def upsert_relationship(store: dict, entity: str, rel_type: str,
                        description: str, sentiment: float = 0.0):
    store["relationships"][entity] = {
        "type": rel_type,         # e.g. "friend", "project", "place"
        "description": description,
        "sentiment": sentiment,   # -1 → +1
        "last_mentioned": datetime.now().isoformat(),
    }


# ── Auto-extraction from messages ─────────────────────────────────────────────

_NAME_RE = re.compile(
    r"(?:my name is|i(?:'m| am)|call me)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", re.I
)
_LIKE_RE = re.compile(r"i (?:love|like|enjoy|adore)\s+(.+?)(?:\.|,|$)", re.I)
_DISLIKE_RE = re.compile(r"i (?:hate|dislike|can't stand|don't like)\s+(.+?)(?:\.|,|$)", re.I)
_GOAL_RE = re.compile(r"(?:i want to|i'm trying to|my goal is to|i plan to)\s+(.+?)(?:\.|,|$)", re.I)
_BIRTHDAY_RE = re.compile(r"(?:my birthday|i was born)[^0-9]*(\d{1,2}[\/\-]\d{1,2}[\/\-]?\d{0,4})", re.I)


def extract_and_store(store: dict, user_text: str, episode_id: Optional[str] = None):
    """Parse user message and persist extracted facts into memory."""

    # Name
    m = _NAME_RE.search(user_text)
    if m:
        name = m.group(1).strip()
        store["user_profile"]["name"] = name
        set_fact(store, "user_name", name, 0.99, episode_id)

    # Likes
    for m in _LIKE_RE.finditer(user_text):
        item = m.group(1).strip().rstrip(".")
        if item and item not in store["user_profile"]["interests"]:
            store["user_profile"]["interests"].append(item)

    # Dislikes
    for m in _DISLIKE_RE.finditer(user_text):
        item = m.group(1).strip().rstrip(".")
        if item and item not in store["user_profile"]["dislikes"]:
            store["user_profile"]["dislikes"].append(item)

    # Goals
    for m in _GOAL_RE.finditer(user_text):
        goal = m.group(1).strip().rstrip(".")
        if goal and goal not in store["user_profile"]["goals"]:
            store["user_profile"]["goals"].append(goal)

    # Birthday
    m = _BIRTHDAY_RE.search(user_text)
    if m and not store["user_profile"]["birthday"]:
        store["user_profile"]["birthday"] = m.group(1)
        set_fact(store, "birthday", m.group(1), 0.9, episode_id)


# ── Memory context builder (injected into system prompt) ──────────────────────

def build_memory_context(store: dict, current_query: str) -> str:
    profile = store["user_profile"]
    lines = []

    name = profile.get("name") or profile.get("preferred_name")
    if name:
        lines.append(f"The user's name is {name}.")

    if profile["interests"]:
        lines.append(f"Known interests: {', '.join(profile['interests'][:8])}.")

    if profile["dislikes"]:
        lines.append(f"Known dislikes: {', '.join(profile['dislikes'][:5])}.")

    if profile["goals"]:
        lines.append(f"Current goals: {', '.join(profile['goals'][:5])}.")

    if profile["birthday"]:
        lines.append(f"Birthday: {profile['birthday']}.")

    # Relevant episodic memories
    relevant = retrieve_relevant_episodes(store, current_query, top_k=4)
    if relevant:
        lines.append("\nRelevant memories from past conversations:")
        for ep in relevant:
            lines.append(f"  [{ep['timestamp'][:10]}] {ep['summary']}")

    # Recent emotional arc
    mood = current_mood_summary(store)
    if mood != "neutral and steady":
        lines.append(f"\nRecent emotional tone: {mood}.")

    # Key semantic facts
    key_facts = {k: v["value"] for k, v in store["semantic"].items()
                 if k not in ("user_name", "birthday") and v["confidence"] > 0.7}
    if key_facts:
        fact_str = "; ".join(f"{k}={v}" for k, v in list(key_facts.items())[:6])
        lines.append(f"Other known facts: {fact_str}.")

    # Relationships
    rels = store.get("relationships", {})
    if rels:
        rel_str = "; ".join(f"{e} ({r['type']})" for e, r in list(rels.items())[:4])
        lines.append(f"Known entities: {rel_str}.")

    return "\n".join(lines) if lines else ""


# ── Session bookkeeping ───────────────────────────────────────────────────────

def begin_session(store: dict):
    store["stats"]["sessions"] += 1
    store["stats"]["last_seen"] = datetime.now().isoformat()


def increment_messages(store: dict):
    store["stats"]["total_messages"] += 1