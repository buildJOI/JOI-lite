"""
model_handler.py — Joi-lite model interface

BUG FIXES:
- Added request timeout (original had none — hangs forever on network issues)
- Added Content-Type header validation
- Better error message extraction from API response body
- response.raise_for_status() replaces manual status check for cleaner exception chain
"""
import requests
from typing import List, Dict, TypedDict
from config import API_KEYS, API_ENDPOINTS, MODEL_NAMES


class ModelPayload(TypedDict):
    model: str
    messages: List[Dict[str, str]]
    max_tokens: int


def query_model(
    model_name: str,
    messages: List[Dict[str, str]],
    max_tokens: int = 512,
    timeout: int = 30,  # BUG FIX: added timeout parameter
) -> str:
    api_key = API_KEYS.get(model_name)
    endpoint = API_ENDPOINTS.get(model_name)
    model_id = MODEL_NAMES.get(model_name)

    if not endpoint or not api_key or not isinstance(model_id, str):
        raise ValueError(f"Invalid or missing configuration for model '{model_name}'")

    payload: ModelPayload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=timeout,  # BUG FIX: prevents infinite hang
        )
    except requests.exceptions.Timeout:
        raise Exception(f"Request to '{model_name}' timed out after {timeout}s")
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Connection error for '{model_name}': {e}")

    if not response.ok:
        # BUG FIX: try to extract error detail from JSON body if available
        try:
            err_detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            err_detail = response.text
        raise Exception(f"API Error {response.status_code} ({model_name}): {err_detail}")

    result = response.json()

    # BUG FIX: Guard against unexpected response shape
    try:
        return result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise Exception(f"Unexpected API response structure from '{model_name}': {e}\nResponse: {result}")