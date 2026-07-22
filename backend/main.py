import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import create_tables, test_connection
from models import Company, Document, DocumentChunk, Question
from routers import companies, documents, questions        

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Stock Research Assistant",
    description="RAG-powered financial document search",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(companies.router)
app.include_router(documents.router)
app.include_router(questions.router)                      

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

@app.on_event("startup")
def startup():
    test_connection()
    create_tables()
    logger.info("✅ Tables ready")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Stock Research API is running"}

@app.get("/health")
def health():
    from sqlalchemy import text
    from database import engine
    checks = {"api": "ok", "database": "unknown"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}