import asyncio
from services.news_fetcher import fetch_news

async def test():
    print("=== Testing News Fetcher ===\n")

    articles = await fetch_news("Apple Inc", "AAPL", days_back=30)

    print(f"Total articles: {len(articles)}\n")

    for i, a in enumerate(articles[:3]):
        print(f"Article {i+1}:")
        print(f"  Title: {a['title']}")
        print(f"  Date:  {a['filing_date']}")
        print(f"  URL:   {a['source_url']}")
        print(f"  Words: {len(a['raw_text'].split())}")
        print(f"  Preview: {a['raw_text'][:150]}")
        print()

asyncio.run(test())