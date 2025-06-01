import requests

def search_web(query: str) -> str:
    API_KEY = "your-api-key"
    SEARCH_URL = "https://api.serper.dev/search"  # Or use another source

    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "q": query
    }

    response = requests.post(SEARCH_URL, headers=headers, json=data)

    if response.status_code == 200:
        results = response.json()
        if results["organic"]:
            top_result = results["organic"][0]
            return f"{top_result['title']}: {top_result['snippet']} (Source: {top_result['link']})"
        else:
            return "No relevant results found."
    else:
        return f"Search failed with status {response.status_code}"
