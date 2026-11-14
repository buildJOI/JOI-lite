import httpx
from config import SERPER_API_KEY


async def web_search(query: str, num_results: int = 5) -> str:
    """
    Perform a live web search via Serper API.
    Returns a formatted string summary, or a graceful message if unavailable.

    Fix: uses httpx.AsyncClient — no blocking calls inside async context.
    """
    if not SERPER_API_KEY:
        return "[Web search unavailable — SERPER_API_KEY not set]"

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://google.serper.dev/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("organic", [])
        if not results:
            return "[No search results found]"

        lines = [f"🔍 Web results for: {query}\n"]
        for i, r in enumerate(results[:num_results], 1):
            title = r.get("title", "No title")
            snippet = r.get("snippet", "")
            link = r.get("link", "")
            lines.append(f"{i}. **{title}**\n   {snippet}\n   {link}\n")

        return "\n".join(lines)

    except Exception as e:
        return f"[Search error: {e}]"