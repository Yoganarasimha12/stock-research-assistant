# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware 

# app = FastAPI(title="Stock Research API")

# # This allows your React frontend to talk to this backend later
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ── Health check ──────────────────────────────────────────
# @app.get("/")
# def health_check():
#     return {"status": "ok", "message": "Stock Research API is running"}


# # ── Company search (mock data for now, real DB later) ─────
# @app.get("/companies/search")
# def search_company(q: str):
#     # This is a dict of dicts — same pattern you just practiced
#     companies = [
#         {"ticker": "AAPL", "name": "Apple Inc"},
#         {"ticker": "TSLA", "name": "Tesla Inc"},
#         {"ticker": "NVDA", "name": "NVIDIA Corporation"},
#         {"ticker": "MSFT", "name": "Microsoft Corporation"},
#         {"ticker": "GOOGL", "name": "Alphabet Inc"},
#     ]

#     # List comprehension — filter companies matching the query
#     results = [
#         c for c in companies
#         if q.lower() in c["name"].lower() or q.lower() in c["ticker"].lower()
#     ]

#     return {"query": q, "results": results}


### with database and docker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import create_tables, test_connection
from models import Company, Document, DocumentChunk, Question

app = FastAPI(
    title="Stock Research Assistant",
    description="RAG-powered financial document search",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    test_connection()   # check DB is reachable
    create_tables()     # create tables if they don't exist
    print("✅ Tables created")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Research API is running"}

@app.get("/companies/search")
def search_company(q: str):
    companies = [
        {"ticker": "AAPL", "name": "Apple Inc"},
        {"ticker": "TSLA", "name": "Tesla Inc"},
        {"ticker": "NVDA", "name": "NVIDIA Corporation"},
        {"ticker": "MSFT", "name": "Microsoft Corporation"},
        {"ticker": "GOOGL", "name": "Alphabet Inc"},
    ]
    results = [
        c for c in companies
        if q.lower() in c["name"].lower() or q.lower() in c["ticker"].lower()
    ]
    return {"query": q, "results": results}