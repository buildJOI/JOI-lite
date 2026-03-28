from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict
import uvicorn
import os
from model_handler import query_model

app = FastAPI()

# Allow browser requests during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists before mounting
if not os.path.isdir("static"):
    os.makedirs("static", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    model: str = "deepseek"
    messages: List[Dict[str, str]] = Field(default_factory=list)


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>JOI Chat</h1><p>Create static/index.html to use the web UI.</p>")


@app.post("/chat")
async def chat(body: ChatRequest):
    model = body.model
    messages = body.messages
    try:
        # query_model is synchronous; keep call simple
        reply = query_model(model, messages)
        return JSONResponse({"reply": reply})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    # Use import string so `--reload` works
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)