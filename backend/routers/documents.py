import logging
import yfinance as yf
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Company, Document
from services.sec_fetcher import fetch_company_filings
from services.news_fetcher import fetch_news

router = APIRouter(prefix="/companies", tags=["ingestion"])
logger = logging.getLogger(__name__)


# ── Background task: does the actual heavy work ───────────
async def run_ingestion(company_id: int, ticker: str, db: Session):
    """
    Runs after API responds — fetches all docs and saves to DB.
    Updates ingestion_status so frontend can poll progress.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    try:
        all_docs = []

        # 1. Fetch SEC filings
        logger.info(f"Fetching SEC filings for {ticker}...")
        filings = await fetch_company_filings(ticker, ["10-K", "10-Q"])
        all_docs.extend(filings)
        logger.info(f"Got {len(filings)} SEC filings")

        # 2. Fetch news articles
        logger.info(f"Fetching news for {ticker}...")
        news = await fetch_news(company.name, ticker)
        all_docs.extend(news)
        logger.info(f"Got {len(news)} news articles")

        # 3. Save all to PostgreSQL
        saved = 0
        skipped = 0
        for doc_data in all_docs:
            # Skip if already ingested (check by source_url)
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
            saved += 1

        db.commit()
        logger.info(f"Saved {saved} docs, skipped {skipped} duplicates")

        # 4. Mark ingestion complete
        company.ingestion_status = "done"
        db.commit()
        logger.info(f"✅ Ingestion complete for {ticker}")

    except Exception as e:
        # Mark as failed so frontend knows something went wrong
        company.ingestion_status = "failed"
        db.commit()
        logger.error(f"❌ Ingestion failed for {ticker}: {e}")


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