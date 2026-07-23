import logging
import yfinance as yf
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Company, Document
from services.sec_fetcher import fetch_company_filings
from services.news_fetcher import fetch_news
from services.chunker import chunk_document
from services.embedder import embed_and_store
from services.embedder import get_collection_stats
from services.retriever import retrieve as retrieve_chunks

router = APIRouter(prefix="/companies", tags=["ingestion"])
logger = logging.getLogger(__name__)


# ── Background task: does the actual heavy work ───────────
async def run_ingestion(company_id: int, ticker: str, db: Session):
    company = db.query(Company).filter(Company.id == company_id).first()

    try:
        all_docs = []

        # 1. Fetch SEC filings
        logger.info(f"Fetching SEC filings for {ticker}...")
        filings = await fetch_company_filings(ticker, ["10-K", "10-Q"])
        all_docs.extend(filings)
        logger.info(f"Got {len(filings)} SEC filings")

        # 2. Fetch news
        logger.info(f"Fetching news for {ticker}...")
        news = await fetch_news(company.name, ticker)
        all_docs.extend(news)
        logger.info(f"Got {len(news)} news articles")

        # 3. Save raw documents to PostgreSQL
        saved_docs = []
        skipped = 0
        for doc_data in all_docs:
            exists = db.query(Document).filter(
                Document.company_id == company_id,
                Document.source_url == doc_data["source_url"]
            ).first()
            if exists:
                skipped += 1
                continue
            doc = Document(
                company_id=company_id,
                doc_type=doc_data["doc_type"],
                title=doc_data["title"],
                source_url=doc_data["source_url"],
                raw_text=doc_data["raw_text"],
                filing_date=doc_data["filing_date"],
            )
            db.add(doc)
            db.flush()        # get doc.id without full commit
            saved_docs.append(doc)

        db.commit()
        logger.info(f"Saved {len(saved_docs)} docs, skipped {skipped} duplicates")

        # 4. Chunk + embed each document
        total_chunks = 0
        for doc in saved_docs:
            chunks = chunk_document(doc)
            count = embed_and_store(chunks, db)
            total_chunks += count
            logger.info(f"Embedded {count} chunks from {doc.doc_type}: {doc.title}")

        # 5. Mark done
        company.ingestion_status = "done"
        db.commit()
        logger.info(f"✅ Ingestion complete for {ticker}: {len(saved_docs)} docs, {total_chunks} chunks")

    except Exception as e:
        company.ingestion_status = "failed"
        db.commit()
        logger.error(f"❌ Ingestion failed for {ticker}: {e}")
        raise


# ── Trigger ingestion endpoint ────────────────────────────
@router.post("/{ticker}/ingest")
async def ingest_company(
    ticker: str,
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Starts ingestion in the background.
    Returns immediately with status "started".
    Poll GET /companies/{ticker} to check progress.

    force=True clears existing docs and re-ingests from scratch.
    """
    ticker = ticker.upper()

    # Get or create company
    company = db.query(Company).filter(Company.ticker == ticker).first()
    if not company:
        try:
            info = yf.Ticker(ticker).info
            name = info.get("longName", ticker)
            sector = info.get("sector")
        except:
            name = ticker
            sector = None

        company = Company(ticker=ticker, name=name, sector=sector)
        db.add(company)
        db.commit()
        db.refresh(company)

    # Don't re-ingest if already running
    if company.ingestion_status == "running" and not force:
        return {
            "status": "already_running",
            "ticker": ticker,
            "message": "Ingestion already in progress. Poll GET /companies/{ticker} for status."
        }

    # Force re-ingest: clear existing documents
    if force:
        deleted = db.query(Document).filter(
            Document.company_id == company.id
        ).delete()
        db.commit()
        logger.info(f"Force re-ingest: deleted {deleted} existing docs for {ticker}")

    # Set status to running
    company.ingestion_status = "running"
    db.commit()

    # Add heavy work to background — API returns immediately
    background_tasks.add_task(run_ingestion, company.id, ticker, db)

    return {
        "status": "started",
        "ticker": ticker,
        "company_id": company.id,
        "message": "Ingestion started. Poll GET /companies/{ticker} to check status."
    }


# ── List documents for a company ─────────────────────────
@router.get("/{ticker}/documents")
def list_documents(
    ticker: str,
    doc_type: str = None,
    db: Session = Depends(get_db)
):
    """
    List all ingested documents for a company.
    Optional filter: ?doc_type=10-K or ?doc_type=news
    """
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = db.query(Document).filter(Document.company_id == company.id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)

    docs = query.order_by(Document.filing_date.desc()).all()

    return {
        "ticker": ticker.upper(),
        "total": len(docs),
        "documents": [
            {
                "id": d.id,
                "type": d.doc_type,
                "title": d.title,
                "date": str(d.filing_date)[:10],
                "word_count": len(d.raw_text.split()) if d.raw_text else 0,
                "source_url": d.source_url,
            }
            for d in docs
        ]
    }


# ── Get ingestion status ──────────────────────────────────
@router.get("/{ticker}/status")
def get_status(ticker: str, db: Session = Depends(get_db)):
    """
    Quick status check for polling.
    Returns: pending | running | done | failed
    """
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Count documents if done
    doc_count = 0
    if company.ingestion_status == "done":
        doc_count = db.query(Document).filter(
            Document.company_id == company.id
        ).count()

    return {
        "ticker": ticker.upper(),
        "status": company.ingestion_status,
        "documents_saved": doc_count,
    }
    
 # ── Chroma stats endpoint ──────────────────────────────────
@router.get("/chroma/stats")
def chroma_stats():
    """How many chunks are stored in the vector database"""
    return get_collection_stats()

@router.get("/{ticker}/retrieve")
def test_retrieve(
    ticker: str,
    q: str,
    doc_type: str = None,
    db: Session = Depends(get_db)
):
    """
    Test retrieval — see what chunks come back for a query.
    Use this to verify RAG quality before adding generation.
    """
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    chunks = retrieve_chunks(
        query=q,
        company_id=company.id,
        doc_type_filter=doc_type
    )

    return {
        "query": q,
        "company": ticker.upper(),
        "doc_type_filter": doc_type,
        "total_retrieved": len(chunks),
        "chunks": [
            {
                "rank": c["rank"],
                "similarity": c["similarity"],
                "final_score": c["final_score"],
                "doc_type": c["doc_type"],
                "date": str(c["filing_date"])[:10],
                "text_preview": c["text"][:300],
                "source_url": c["source_url"],
            }
            for c in chunks
        ]
    }
    
#temporary endpoint to clear all documents for a company (for testing)
@router.get("/chroma/debug")
def chroma_debug():
    """Check what metadata is actually stored in Chroma"""
    from services.embedder import get_chroma_collection
    collection = get_chroma_collection()

    # Get first 5 chunks and show their metadata
    results = collection.get(limit=5, include=["metadatas"])

    return {
        "total_chunks": collection.count(),
        "sample_metadatas": results["metadatas"]
    }