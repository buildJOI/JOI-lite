```python
import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, List

# Your existing modules
from model_handler import get_joi_response

# NEW: Semantic memory
from memory import retrieve_memory, store_memory

app = FastAPI()

# -------------------------------
# Session Storage (Short-term memory)
# -------------------------------
_sessions: Dict[str, List[Dict[str, str]]] = {}


# -------------------------------
# Request Model
# -------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    mood: Optional[str] = "default"


# -------------------------------
# Root Endpoint
# -------------------------------
@app.get("/")
def root():
    return {"message": "JOI-lite API is running"}


# -------------------------------
# Chat Endpoint (CORE LOGIC)
# -------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    user_text = req.message

    # -------------------------------
    # Session Handling
    # -------------------------------
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in _sessions:
        _sessions[session_id] = []

    history = _sessions[session_id]

    # -------------------------------
    # 🔥 STEP 1: Retrieve Semantic Memory
    # -------------------------------
    relevant_memories = retrieve_memory(user_text)

    memory_context = ""
    if relevant_memories:
        memory_context = "\n".join(
            [f"- {mem}" for mem in relevant_memories]
        )

    # -------------------------------
    # 🔥 STEP 2: Build Augmented Prompt
    # -------------------------------
    augmented_prompt = f"""
You are JOI, an adaptive AI assistant.

Relevant past information about the user:
{memory_context if memory_context else "None"}

Now respond naturally to the user.

User: {user_text}
"""

    # -------------------------------
    # STEP 3: Call LLM
    # -------------------------------
    joi_response = await get_joi_response(
        user_message=augmented_prompt,
        conversation_history=history,
        mood=req.mood,
    )

    # -------------------------------
    # STEP 4: Update Session Memory
    # -------------------------------
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": joi_response})

    # -------------------------------
    # 🔥 STEP 5: Store Semantic Memory
    # -------------------------------
    try:
        # You can improve this later with filtering
        store_memory(user_text)
    except Exception as e:
        print(f"[Memory Error] {e}")

    # -------------------------------
    # Response
    # -------------------------------
    return {
        "session_id": session_id,
        "response": joi_response
    }


# -------------------------------
# Optional: View Memory (Debug)
# -------------------------------
@app.get("/memory")
def view_memory():
    try:
        import json
        with open("memory.json", "r") as f:
            data = json.load(f)
        return data
    except:
        return {"message": "No memory found"}


# -------------------------------
# Optional: Clear Memory
# -------------------------------
@app.delete("/memory")
def clear_memory():
    import os

    try:
        if os.path.exists("memory.json"):
            os.remove("memory.json")
        if os.path.exists("memory.index"):
            os.remove("memory.index")

        return {"message": "Memory cleared"}
    except Exception as e:
        return {"error": str(e)}
```
