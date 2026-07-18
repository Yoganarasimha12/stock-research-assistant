import httpx
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


async def fetch_news(
    company_name: str,
    ticker: str,
    days_back: int = 60
) -> list:
    """
    Fetch recent news articles about a company.
    Returns a list of dicts ready to save as Document records.
    """
    api_key = os.getenv("NEWS_API_KEY")

    # If no API key configured, skip news gracefully
    if not api_key:
        print("⚠️  NEWS_API_KEY not set — skipping news fetch")
        return []

    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    params = {
        "q": f'"{company_name}" OR "{ticker}"',
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 30,
        "apiKey": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                "https://newsapi.org/v2/everything",
                params=params
            )
            data = r.json()
    except Exception as e:
        print(f"⚠️  News fetch failed: {e}")
        return []

    articles = data.get("articles", [])
    results = []

    for a in articles:
        # Skip removed or empty articles
        content = a.get("content", "")
        if not content or "[Removed]" in content:
            continue

        # Combine title + description + content for richer text
        full_text = "\n\n".join(filter(None, [
            a.get("title", ""),
            a.get("description", ""),
            a.get("content", ""),
        ]))

        results.append({
            "doc_type": "news",
            "title": a.get("title", "No title"),
            "raw_text": full_text,
            "filing_date": datetime.fromisoformat(
                a["publishedAt"].replace("Z", "+00:00")
            ),
            "source_url": a.get("url", ""),
        })

    print(f"✅ Fetched {len(results)} news articles for {company_name}")
    return results