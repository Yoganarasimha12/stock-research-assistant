from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Stock Research API")

# This allows your React frontend to talk to this backend later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check ──────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Research API is running"}


# ── Company search (mock data for now, real DB later) ─────
@app.get("/companies/search")
def search_company(q: str):
    # This is a dict of dicts — same pattern you just practiced
    companies = [
        {"ticker": "AAPL", "name": "Apple Inc"},
        {"ticker": "TSLA", "name": "Tesla Inc"},
        {"ticker": "NVDA", "name": "NVIDIA Corporation"},
        {"ticker": "MSFT", "name": "Microsoft Corporation"},
        {"ticker": "GOOGL", "name": "Alphabet Inc"},
    ]

    # List comprehension — filter companies matching the query
    results = [
        c for c in companies
        if q.lower() in c["name"].lower() or q.lower() in c["ticker"].lower()
    ]

    return {"query": q, "results": results}