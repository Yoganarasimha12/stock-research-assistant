import asyncio
from services.sec_fetcher import get_cik, get_recent_filings, fetch_company_filings

async def test():
    print("=== Testing SEC EDGAR Fetcher ===\n")

    # Test 1: Get CIK
    print("1. Getting CIK for AAPL...")
    cik = await get_cik("AAPL")
    print(f"   CIK: {cik}\n")

    # Test 2: Get recent filings list
    print("2. Getting recent 10-K filings...")
    filings = await get_recent_filings(cik, "10-K", count=2)
    for f in filings:
        print(f"   {f['date']} — {f['primary_doc']}")
    print()

    # Test 3: Fetch one full filing
    print("3. Downloading first 10-K (this takes ~10 seconds)...")
    all_docs = await fetch_company_filings("AAPL", filing_types=["10-K"])
    doc = all_docs[0]
    word_count = len(doc["raw_text"].split())
    print(f"   Title: {doc['title']}")
    print(f"   Words: {word_count:,}")
    print(f"   First 300 chars:\n   {doc['raw_text'][:300]}")

asyncio.run(test())