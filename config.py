"""
config.py — Joi-lite configuration

BUG FIX: Original had the DeepSeek API key hardcoded in plain text — a serious
security issue. Keys should always be loaded from environment variables / .env files.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file automatically

API_KEYS = {
    "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
}

API_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
}

MODEL_NAMES = {
    "deepseek": "deepseek-chat",
}

# Validate on import so failures are caught early
for name, key in API_KEYS.items():
    if not key:
        import warnings
        warnings.warn(
            f"[config] API key for '{name}' is not set. "
            f"Add {name.upper()}_API_KEY to your .env file.",
            stacklevel=2,
        )