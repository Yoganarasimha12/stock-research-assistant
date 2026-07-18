from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import create_tables, test_connection
from models import Company, Document, DocumentChunk, Question
from routers import companies

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

# Register routers
app.include_router(companies.router)

@app.on_event("startup")
def startup():
    test_connection()
    create_tables()
    print("✅ Tables created")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Research API is running"}