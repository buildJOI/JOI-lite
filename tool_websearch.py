import os
import requests
from dotenv import load_dotenv
 
load_dotenv()
 
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SEARCH_URL = "https://api.serper.dev/search"
 
 
def search_web(query: str, num_results: int = 3) -> str:
    if not SERPER_API_KEY:
        return "[Web search unavailable: SERPER_API_KEY not set in .env]"
 
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    data = {"q": query, "num": num_results}
 
    try:
        response = requests.post(SEARCH_URL, headers=headers, json=data, timeout=10)
    except requests.exceptions.Timeout:
        return "[Web search timed out]"
    except requests.exceptions.ConnectionError:
        return "[Web search failed: no internet connection]"
 
    if response.status_code != 200:
        return f"[Search failed: HTTP {response.status_code}]"
 
    results = response.json()
    organic = results.get("organic", [])  # BUG FIX: was results["organic"] — KeyError if absent
 
    if not organic:
        return "No relevant results found."
 
    # BUG FIX: Return top N results instead of just 1
    snippets = []
    for item in organic[:num_results]:
        title = item.get("title", "No title")
        snippet = item.get("snippet", "No snippet")
        link = item.get("link", "")
        snippets.append(f"• {title}: {snippet} ({link})")
 
    return "\n".join(snippets)
