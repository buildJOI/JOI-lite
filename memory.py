```python
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import os
from datetime import datetime

# -------------------------------
# MODEL
# -------------------------------
model = SentenceTransformer('all-MiniLM-L6-v2')

INDEX_FILE = "memory.index"
DATA_FILE = "memory.json"

# -------------------------------
# LOAD / INIT
# -------------------------------
if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
else:
    index = faiss.IndexFlatL2(384)

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        memory_data = json.load(f)
else:
    memory_data = []


# -------------------------------
# 🧠 CLASSIFICATION LOGIC
# -------------------------------
def classify_memory(text):
    text_lower = text.lower()

    if any(word in text_lower for word in ["love", "like", "enjoy"]):
        return "interest"
    elif any(word in text_lower for word in ["goal", "want to", "build", "create"]):
        return "goal"
    elif any(word in text_lower for word in ["prefer", "usually", "always"]):
        return "preference"
    elif any(word in text_lower for word in ["sad", "frustrated", "angry", "tired"]):
        return "emotional"
    
    return "general"


# -------------------------------
# ❤️ EMOTION DETECTION
# -------------------------------
def detect_emotion(text):
    text_lower = text.lower()

    if any(word in text_lower for word in ["happy", "excited", "love"]):
        return "positive"
    elif any(word in text_lower for word in ["sad", "angry", "frustrated", "tired"]):
        return "negative"
    
    return "neutral"


# -------------------------------
# ⭐ IMPORTANCE SCORING
# -------------------------------
def compute_importance(text, memory_type):
    score = 0.5

    if memory_type == "goal":
        score += 0.3
    elif memory_type == "emotional":
        score += 0.2

    if len(text) > 50:
        score += 0.1

    return min(score, 1.0)


# -------------------------------
# 💾 STORE MEMORY
# -------------------------------
def store_memory(text):
    memory_type = classify_memory(text)
    emotion = detect_emotion(text)
    importance = compute_importance(text, memory_type)

    # Filter out useless memory
    if memory_type == "general" and importance < 0.6:
        return

    embedding = model.encode([text])[0].astype("float32")
    index.add(np.array([embedding]))

    memory_entry = {
        "text": text,
        "type": memory_type,
        "emotion": emotion,
        "importance": importance,
        "timestamp": datetime.utcnow().isoformat()
    }

    memory_data.append(memory_entry)

    faiss.write_index(index, INDEX_FILE)
    with open(DATA_FILE, "w") as f:
        json.dump(memory_data, f, indent=2)


# -------------------------------
# 🔍 RETRIEVE MEMORY (SMART)
# -------------------------------
def retrieve_memory(query, k=5):
    if len(memory_data) == 0:
        return []

    query_vec = model.encode([query]).astype("float32")
    D, I = index.search(query_vec, k)

    results = []

    for i, idx in enumerate(I[0]):
        if idx < len(memory_data):
            mem = memory_data[idx]

            # Combine similarity + importance
            similarity_score = 1 / (1 + D[0][i])
            final_score = similarity_score * 0.7 + mem["importance"] * 0.3

            results.append((final_score, mem))

    # Sort by final score
    results.sort(key=lambda x: x[0], reverse=True)

    # Return formatted memory
    return [
        f"{mem['text']} (type: {mem['type']}, emotion: {mem['emotion']})"
        for _, mem in results[:3]
    ]