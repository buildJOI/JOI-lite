import requests
from typing import List, Dict, TypedDict
from config import API_KEYS, API_ENDPOINTS, MODEL_NAMES 

class ModelPayload(TypedDict):
    model: str
    messages: List[Dict[str, str]]
    max_tokens: int

def query_model(model_name: str, messages: List[Dict[str, str]], max_tokens: int = 512) -> str:
    api_key = API_KEYS.get(model_name)
    endpoint = API_ENDPOINTS.get(model_name)
    model_id = MODEL_NAMES.get(model_name)

    if not endpoint or not api_key or not isinstance(model_id, str):
        raise ValueError(f"Invalid configuration for model '{model_name}'")

    payload: ModelPayload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(endpoint, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()
