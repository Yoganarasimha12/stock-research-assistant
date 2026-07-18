import httpx
import re
from typing import Optional
from datetime import datetime
import asyncio

# SEC requires this header — they block requests without it
HEADERS = {"User-Agent": "yourname@youremail.com"}


# ── Step A: Convert ticker (AAPL) to SEC CIK number ──────
async def get_cik(ticker: str) -> Optional[str]:
    url = "https://www.sec.gov/files/company_tickers.json"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=HEADERS)
        data = r.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    return None


# ── Step B: Get list of recent filings ───────────────────
async def get_recent_filings(
    cik: str,
    filing_type: str = "10-K",
    count: int = 3
) -> list:
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=HEADERS)
        data = r.json()

    filings = data["filings"]["recent"]
    results = []
    for i, form in enumerate(filings["form"]):
        if form == filing_type:
            results.append({
                "accession": filings["accessionNumber"][i].replace("-", ""),
                "date": filings["filingDate"][i],
                "primary_doc": filings["primaryDocument"][i],
            })
        if len(results) >= count:
            break
    return results


# ── Step C: Get filing index to find readable document ───
async def get_filing_index(cik: str, accession: str) -> list:
    """
    Get list of all documents inside a filing.
    Primary document is often XBRL — we need the readable HTML.
    """
    acc_dashed = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    cik_int = int(cik)
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{acc_dashed}-index.json"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=HEADERS)
        if r.status_code != 200:
            return []
        data = r.json()
    return data.get("documents", [])


# ── Step D: Find the human-readable filing document ──────
async def find_readable_doc(cik: str, accession: str, filing_type: str) -> str:
    """
    Find the actual readable filing (not XBRL gibberish).
    Returns the filename.
    """
    documents = await get_filing_index(cik, accession)

    # First: look for document with exact type match
    for doc in documents:
        if doc.get("type") == filing_type:
            return doc.get("name", "")

    # Fallback: find largest .htm file (usually the full filing)
    htm_docs = [
        d for d in documents
        if d.get("name", "").endswith(".htm")
        and "xbrl" not in d.get("name", "").lower()
    ]
    if htm_docs:
        largest = max(htm_docs, key=lambda d: d.get("size", 0))
        return largest.get("name", "")

    return ""


# ── Step E: Download the actual filing text ───────────────
async def fetch_filing_text(
    cik: str,
    accession: str,
    doc: str,
    filing_type: str = "10-K"
) -> str:
    """
    Download the filing, extract clean text using BeautifulSoup.
    Handles inline XBRL format which regex can't clean properly.
    """
    readable_doc = await find_readable_doc(cik, accession, filing_type)
    if readable_doc:
        doc = readable_doc

    cik_int = int(cik)
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{doc}"

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(url, headers=HEADERS)

    # Use BeautifulSoup instead of regex — handles XBRL properly
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")

    # Remove tags that contain noise, not readable content
    for tag in soup(["script", "style", "ix:header", "ix:hidden", "ix:resources"]):
        tag.decompose()

    # Extract clean text
    text = soup.get_text(separator=" ", strip=True)

    # Collapse extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate very long filings
    words = text.split()
    if len(words) > 80000:
        text = " ".join(words[:80000])

    return text


# ── Step F: Retry wrapper ─────────────────────────────────
async def fetch_with_retry(url: str, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url, headers=HEADERS)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"Retry {attempt + 1} after {wait}s: {e}")
            await asyncio.sleep(wait)


# ── Main entry: fetch all filings for a company ──────────
async def fetch_company_filings(
    ticker: str,
    filing_types: list = None
) -> list:
    if filing_types is None:
        filing_types = ["10-K", "10-Q"]

    cik = await get_cik(ticker)
    if not cik:
        raise ValueError(f"Could not find SEC CIK for ticker: {ticker}")

    print(f"Found CIK for {ticker}: {cik}")
    all_filings = []

    for filing_type in filing_types:
        count = 3 if filing_type == "10-K" else 4
        filings = await get_recent_filings(cik, filing_type, count=count)
        print(f"Found {len(filings)} {filing_type} filings")

        for f in filings:
            print(f"  Downloading {filing_type} from {f['date']}...")
            text = await fetch_filing_text(
                cik, f["accession"], f["primary_doc"], filing_type
            )
            all_filings.append({
                "doc_type": filing_type,
                "title": f"{ticker} {filing_type} ({f['date']})",
                "raw_text": text,
                "filing_date": datetime.strptime(f["date"], "%Y-%m-%d"),
                "source_url": (
                    f"https://www.sec.gov/Archives/edgar/data/"
                    f"{int(cik)}/{f['accession']}/{f['primary_doc']}"
                ),
            })

    return all_filings