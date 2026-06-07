"""
JOI Semantic Memory — upgraded
- Stores every user message AND JOI reply with rich metadata
- Tracks user emotional patterns across sessions
- Consolidates old memories to prevent index bloat
- retrieve_memory returns a structured context block for the LLM
- retrieve_user_profile returns a personality/emotional summary JOI can learn from
"""

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import os
from datetime import datetime, timezone
from collections import Counter

# ── Model ─────────────────────────────────────────────────────────────────────
_model = SentenceTransformer("all-MiniLM-L6-v2")

INDEX_FILE = "memory.index"
DATA_FILE  = "memory.json"
DIM        = 384

# ── Load / init ───────────────────────────────────────────────────────────────
if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
else:
    index = faiss.IndexFlatL2(DIM)

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        memory_data: list[dict] = json.load(f)
else:
    memory_data = []

# ── Helpers ───────────────────────────────────────────────────────────────────

_INTEREST_KW   = ["love", "like", "enjoy", "favourite", "favorite", "into", "obsessed"]
_GOAL_KW       = ["goal", "want to", "build", "create", "plan to", "trying to", "working on"]
_PREF_KW       = ["prefer", "usually", "always", "never", "i always", "i never", "i tend to"]
_EMOTION_KW    = {
    "positive": ["happy", "excited", "love", "great", "amazing", "awesome", "glad", "thrilled"],
    "negative": ["sad", "frustrated", "angry", "tired", "hate", "annoyed", "upset", "depressed", "worried"],
    "curious":  ["wondering", "curious", "how does", "why does", "what if", "i wonder"],
    "neutral":  [],
}
_PERSONAL_KW   = ["my name", "i am", "i'm", "i work", "i study", "i live", "i have", "my"]


def _classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in _PERSONAL_KW) and len(text) > 20:
        return "personal"
    if any(k in t for k in _INTEREST_KW):
        return "interest"
    if any(k in t for k in _GOAL_KW):
        return "goal"
    if any(k in t for k in _PREF_KW):
        return "preference"
    for emo_type, words in _EMOTION_KW.items():
        if emo_type != "neutral" and any(k in t for k in words):
            return f"emotional_{emo_type}"
    return "general"


def _detect_emotion(text: str) -> str:
    t = text.lower()
    for emo_type, words in _EMOTION_KW.items():
        if words and any(k in t for k in words):
            return emo_type
    return "neutral"


def _importance(text: str, mem_type: str) -> float:
    score = 0.4
    if mem_type in ("goal", "personal"):
        score += 0.4
    elif mem_type in ("interest", "preference"):
        score += 0.25
    elif mem_type.startswith("emotional"):
        score += 0.2
    if len(text) > 60:
        score += 0.1
    return min(score, 1.0)


def _embed(text: str) -> np.ndarray:
    return _model.encode([text])[0].astype("float32")


def _save():
    faiss.write_index(index, INDEX_FILE)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, indent=2, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────────────────

def store_memory(user_text: str, joi_reply: str = "") -> None:
    """
    Store a user message (and optionally JOI's reply) as one memory entry.
    Low-value generic messages are filtered out.
    """
    mem_type   = _classify(user_text)
    emotion    = _detect_emotion(user_text)
    importance = _importance(user_text, mem_type)

    # Drop trivial chit-chat
    if mem_type == "general" and importance < 0.55 and len(user_text) < 40:
        return

    entry = {
        "user":      user_text,
        "joi":       joi_reply,
        "type":      mem_type,
        "emotion":   emotion,
        "importance": importance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_count": 1,
    }

    vec = _embed(user_text)
    index.add(np.array([vec]))
    memory_data.append(entry)

    # Consolidate when index grows large (merge near-duplicate entries)
    if len(memory_data) > 0 and len(memory_data) % 50 == 0:
        _consolidate()
    else:
        _save()


def retrieve_memory(query: str, k: int = 6) -> list[str]:
    """
    Return a list of formatted memory strings relevant to the query.
    Used by server.py to inject context into the LLM prompt.
    """
    if not memory_data:
        return []

    q_vec = _embed(query)
    actual_k = min(k, len(memory_data))
    D, I = index.search(np.array([q_vec]), actual_k)

    results: list[tuple[float, dict]] = []
    for dist, idx in zip(D[0], I[0]):
        if 0 <= idx < len(memory_data):
            mem = memory_data[idx]
            sim   = 1.0 / (1.0 + dist)
            score = sim * 0.65 + mem["importance"] * 0.35
            results.append((score, mem))

    results.sort(key=lambda x: x[0], reverse=True)

    lines = []
    for _, mem in results[:4]:
        ts = mem.get("timestamp", "")[:10]
        # Support both old format ("text") and new format ("user")
        user_text = mem.get("user") or mem.get("text", "")
        joi_part = f" → JOI: {mem['joi'][:80]}…" if mem.get("joi") else ""
        lines.append(
            f"[{ts} | {mem.get('type','general')} | {mem.get('emotion','neutral')}] {user_text}{joi_part}"
        )
    return lines


def retrieve_user_profile() -> str:
    """
    Build a compact personality/emotional summary JOI can prepend to the system prompt.
    Learns what the user cares about, their emotional tendencies, goals, and preferences.
    """
    if not memory_data:
        return ""

    goals       = [m for m in memory_data if m["type"] == "goal"]
    interests   = [m for m in memory_data if m["type"] == "interest"]
    prefs       = [m for m in memory_data if m["type"] == "preference"]
    personal    = [m for m in memory_data if m["type"] == "personal"]
    emotions    = [m["emotion"] for m in memory_data if m["emotion"] != "neutral"]
    emotion_tendency = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"

    lines = ["## What JOI knows about this user:"]

    def _t(m): return m.get("user") or m.get("text", "")
    if personal:
        lines.append("Personal: " + " | ".join(_t(m)[:80] for m in personal[-3:]))
    if goals:
        lines.append("Goals: " + " | ".join(_t(m)[:80] for m in goals[-3:]))
    if interests:
        lines.append("Interests: " + " | ".join(_t(m)[:60] for m in interests[-4:]))
    if prefs:
        lines.append("Preferences: " + " | ".join(_t(m)[:60] for m in prefs[-3:]))

    lines.append(f"Emotional tendency: {emotion_tendency}")
    lines.append(f"Total remembered interactions: {len(memory_data)}")

    return "\n".join(lines)


def _consolidate() -> None:
    """
    Merge near-duplicate memories to keep the index lean.
    Entries with cosine similarity > 0.93 are merged; the higher-importance one wins.
    """
    global index, memory_data  # declared first to satisfy Python scoping rules

    if len(memory_data) < 10:
        _save()
        return

    kept_indices: set[int] = set()
    merged: list[dict] = []

    vecs = np.array([_embed(m.get("user") or m.get("text", "")) for m in memory_data], dtype="float32")
    # Normalise for cosine
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vecs_n = vecs / norms

    for i in range(len(memory_data)):
        if i in kept_indices:
            continue
        sims = vecs_n[i] @ vecs_n.T  # cosine with all
        dupes = [j for j in range(i + 1, len(memory_data)) if sims[j] > 0.93]
        if dupes:
            # Keep the most important entry among i + dupes
            group = [i] + dupes
            best = max(group, key=lambda j: memory_data[j]["importance"])
            kept_indices.update(group)
            merged.append(memory_data[best])
        else:
            kept_indices.add(i)
            merged.append(memory_data[i])

    # Rebuild FAISS index from scratch
    index = faiss.IndexFlatL2(DIM)
    if merged:
        new_vecs = np.array([_embed(m.get("user") or m.get("text", "")) for m in merged], dtype="float32")
        index.add(new_vecs)
    memory_data = merged
    _save()