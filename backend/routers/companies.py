import logging
logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Company
import yfinance as yf
from services.sec_fetcher import get_cik, get_recent_filings

router = APIRouter(prefix="/companies", tags=["companies"])


# ── What shape of data we accept for creating a company ──
class CompanyCreate(BaseModel):
    ticker: str
    name: str = None   # optional — we'll fetch from yfinance if not given


# ── CREATE a company ──────────────────────────────────────
@router.post("/")
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(
        Company.ticker == data.ticker.upper()
    ).first()
    if existing:
        logger.info(f"Company {data.ticker} already exists, returning existing")
        return existing

    name = data.name
    sector = None
    if not name:
        try:
            info = yf.Ticker(data.ticker).info
            name = info.get("longName", data.ticker)
            sector = info.get("sector")
            logger.info(f"Fetched info for {data.ticker}: {name}")
        except Exception as e:
            logger.warning(f"yfinance failed for {data.ticker}: {e}")
            name = data.ticker

    company = Company(
        ticker=data.ticker.upper(),
        name=name,
        sector=sector
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    logger.info(f"Created company: {company.ticker}")
    return company


# ── SEARCH companies ──────────────────────────────────────
@router.get("/search")
def search_companies(q: str, db: Session = Depends(get_db)):
    # First search companies already saved in DB
    results = db.query(Company).filter(
        Company.name.ilike(f"%{q}%") | Company.ticker.ilike(f"%{q}%")
    ).limit(10).all()

    # If nothing in DB, try yfinance for ticker lookup
    if not results and len(q) <= 5:
        try:
            info = yf.Ticker(q.upper()).info
            if info.get("longName"):
                results = [{"ticker": q.upper(), "name": info["longName"], "in_db": False}]
        except:
            pass

    return {"results": results}


# ── LIST all companies ────────────────────────────────────
@router.get("/")
def list_companies(db: Session = Depends(get_db)):
    return db.query(Company).all()


# ── GET one company by ticker ─────────────────────────────
@router.get("/{ticker}")
def get_company(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"{ticker} not found. Add it first via POST /companies/"
        )
    return company


# ── UPDATE a company (partial) ────────────────────────────
@router.patch("/{ticker}")
def update_company(
    ticker: str,
    name: str = None,
    sector: str = None,
    db: Session = Depends(get_db)
):
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Not found")
    if name:
        company.name = name
    if sector:
        company.sector = sector
    db.commit()
    db.refresh(company)
    return company


# ── DELETE a company ──────────────────────────────────────
@router.delete("/{ticker}")
def delete_company(ticker: str, db: Session = Depends(get_db)):
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(company)
    db.commit()
    return {"deleted": ticker.upper()}

# ── SEC test endpoint ─────────────────────────────────────
@router.get("/{ticker}/sec-test")
async def test_sec(ticker: str):
    """
    Quick test: verify SEC EDGAR can find this company
    and list its recent filings — without downloading full text
    """
    cik = await get_cik(ticker)
    if not cik:
        raise HTTPException(
            status_code=404,
            detail=f"No SEC CIK found for {ticker}"
        )

    filings_10k = await get_recent_filings(cik, "10-K", count=3)
    filings_10q = await get_recent_filings(cik, "10-Q", count=4)

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "recent_10K": [
            {"date": f["date"], "doc": f["primary_doc"]}
            for f in filings_10k
        ],
        "recent_10Q": [
            {"date": f["date"], "doc": f["primary_doc"]}
            for f in filings_10q
        ],
    }
   
# ── Stock price history ─────────────────────────────────── 
@router.get("/{ticker}/prices")
def get_stock_prices(ticker: str, period: str = "1y"):
    """
    Get historical stock prices.
    period options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    """
    try:
        data = yf.Ticker(ticker.upper()).history(period=period)

        if data.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for {ticker}"
            )

        data = data.reset_index()
        prices = [
            {
                "date": row["Date"].strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
            for _, row in data.iterrows()
        ]

        return {
            "ticker": ticker.upper(),
            "period": period,
            "total_days": len(prices),
            "prices": prices
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Company market info ───────────────────────────────────
@router.get("/{ticker}/info")
def get_company_info(ticker: str):
    """
    Get real-time company stats: market cap, P/E ratio,
    52-week high/low etc.
    """
    try:
        info = yf.Ticker(ticker.upper()).info

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "current_price": info.get("currentPrice"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))