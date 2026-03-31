# server.py
import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from model_handler import query_model  # Ensure this matches your existing import
from voice_handler import generate_joi_audio  # NEW IMPORT

app = FastAPI()

# CORS Settings (Allow Render & Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- YOUR EXISTING MODELS & CONFIG ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    mood: Optional[str] = "default"
    profile: Optional[dict] = None

# --- YOUR EXISTING PERSONALITY LAYERS ---
PERSONALITY_LAYERS = {
    "default": "You are JOI, a compassionate AI companion.",
    "romantic": "You are JOI, deeply affectionate and intimate.",
    "playful": "You are JOI, witty and energetic.",
    "empathetic": "You are JOI, gentle and understanding."
}

# --- HELPER FUNCTIONS (Keep your existing ones) ---
def build_messages(system_prompt, profile, history, user_input):
    # Keep your existing logic here
    messages = [{"role": "system", "content": system_prompt}]
    if profile:
        messages.append({"role": "system", "content": f"User Profile: {profile}"})
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return messages

def format_profile_summary(profile):
    # Keep your existing logic here
    return str(profile)

# --- EXISTING TEXT ENDPOINT ---
@app.post("/chat")
async def chat(body: ChatRequest):
    # Keep your existing logic here
    mood = body.mood if body.mood in PERSONALITY_LAYERS else "default"
    personality_prompt = PERSONALITY_LAYERS[mood]
    profile_summary = format_profile_summary(body.profile) if body.profile else ""
    
    raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]
    if not raw_messages:
        raise HTTPException(status_code=400, detail="messages list is empty")
    
    last_message = raw_messages[-1]
    history = raw_messages[:-1]
    
    full_messages = build_messages(personality_prompt, profile_summary, history, last_message["content"])
    
    try:
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(
            None, lambda: query_model(body.model, full_messages)
        )
        return {"reply": reply, "mood": mood}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- NEW VOICE ENDPOINT ---
@app.post("/chat/voice")
async def chat_with_voice(body: ChatRequest):
    """Chat endpoint that returns text + ElevenLabs audio"""
    mood = body.mood if body.mood in PERSONALITY_LAYERS else "default"
    personality_prompt = PERSONALITY_LAYERS[mood]
    profile_summary = format_profile_summary(body.profile) if body.profile else ""
    
    raw_messages = [{"role": m.role, "content": m.content} for m in body.messages]
    if not raw_messages:
        raise HTTPException(status_code=400, detail="messages list is empty")
    
    last_message = raw_messages[-1]
    history = raw_messages[:-1]
    
    full_messages = build_messages(personality_prompt, profile_summary, history, last_message["content"])
    
    try:
        loop = asyncio.get_event_loop()
        
        # 1. Get Text Reply
        reply = await loop.run_in_executor(
            None, lambda: query_model(body.model, full_messages)
        )
        
        # 2. Generate Audio (Run in thread to avoid blocking)
        audio_b64 = await loop.run_in_executor(
            None, lambda: generate_joi_audio(reply, mood)
        )
        
        response = {"reply": reply, "mood": mood}
        if audio_b64:
            response["audio"] = audio_b64
            response["audio_format"] = "mp3"
        
        return response
        
    except Exception as e:
        print(f"❌ /chat/voice error: {e}")
        # Fallback: return text only
        return {"reply": "I'm here with you.", "mood": "empathetic", "error": "Voice unavailable"}