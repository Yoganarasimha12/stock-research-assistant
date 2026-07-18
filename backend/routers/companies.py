from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Company
import yfinance as yf

router = APIRouter(prefix="/companies", tags=["companies"])


# ── What shape of data we accept for creating a company ──
class CompanyCreate(BaseModel):
    ticker: str
    name: str = None   # optional — we'll fetch from yfinance if not given


# ── CREATE a company ──────────────────────────────────────
@router.post("/")
def create_company(data: CompanyCreate, db: Session = Depends(get_db)):
    # Check if already exists — don't create duplicates
    existing = db.query(Company).filter(
        Company.ticker == data.ticker.upper()
    ).first()
    if existing:
        return existing

    # Fetch real name + sector from yfinance if name not provided
    name = data.name
    sector = None
    if not name:
        try:
            info = yf.Ticker(data.ticker).info
            name = info.get("longName", data.ticker)
            sector = info.get("sector")
        except:
            name = data.ticker

    company = Company(
        ticker=data.ticker.upper(),
        name=name,
        sector=sector
    )
    db.add(company)
    db.commit()
    db.refresh(company)
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