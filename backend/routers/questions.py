import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Company, Question
from services.retriever import retrieve
from services.rag import generate_answer
import json
from fastapi.responses import StreamingResponse
from services.rag import build_context, SYSTEM_PROMPT, groq_client

router = APIRouter(prefix="/companies", tags=["questions"])
logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str
    doc_type: Optional[str] = None   # "10-K", "10-Q", "news" or None for all


@router.post("/{ticker}/ask")
def ask_question(
    ticker: str,
    body: AskRequest,
    db: Session = Depends(get_db)
):
    """
    Ask a question about a company.
    Retrieves relevant chunks then generates a cited answer.
    """
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.ingestion_status != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Ingestion status: {company.ingestion_status}. Wait for ingestion to complete."
        )

    # Step 1: Retrieve relevant chunks
    chunks = retrieve(
        query=body.question,
        company_id=company.id,
        doc_type_filter=body.doc_type
    )

    # Step 2: Generate cited answer
    result = generate_answer(body.question, chunks)

    # Step 3: Save to history
    q = Question(
        company_id=company.id,
        question=body.question,
        answer=result["answer"],
        sources=result["sources"],
        doc_type_filter=body.doc_type,
    )
    db.add(q)
    db.commit()

    logger.info(f"Q&A saved for {ticker}: '{body.question[:50]}'")
    return result


@router.get("/{ticker}/questions")
def get_question_history(
    ticker: str,
    db: Session = Depends(get_db)
):
    """Get all past questions and answers for a company"""
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    qs = db.query(Question).filter(
        Question.company_id == company.id
    ).order_by(Question.asked_at.desc()).limit(20).all()

    return [
        {
            "id": q.id,
            "question": q.question,
            "answer": q.answer,
            "sources": q.sources,
            "doc_type_filter": q.doc_type_filter,
            "asked_at": str(q.asked_at),
        }
        for q in qs
    ]


@router.get("/{ticker}/suggestions")
def get_suggestions(ticker: str):
    """Return 5 good starter questions for this company"""
    return {
        "questions": [
            f"What were {ticker}'s main revenue sources last fiscal year?",
            f"What risks did {ticker} highlight in their most recent filing?",
            f"How has {ticker}'s operating margin changed over recent quarters?",
            f"What did {ticker} management say about AI or technology investments?",
            f"What is {ticker}'s current cash and debt situation?",
        ]
    }
    
@router.post("/{ticker}/ask/stream")
async def ask_stream(
    ticker: str,
    body: AskRequest,
    db: Session = Depends(get_db)
):
    """
    Streaming version of ask — tokens appear word by word.
    Uses Server-Sent Events (SSE) format.
    Frontend connects and reads tokens as they arrive.
    """
    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.ingestion_status != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Ingestion not complete. Status: {company.ingestion_status}"
        )

    # Retrieve chunks upfront (fast — local embedding)
    chunks = retrieve(
        query=body.question,
        company_id=company.id,
        doc_type_filter=body.doc_type
    )

    async def generate():
        # 1. Send sources first as a named event
        sources = [
            {
                "rank": c["rank"],
                "doc_type": c["doc_type"],
                "date": str(c["filing_date"])[:10],
                "url": c["source_url"],
                "chunk_text": c["text"][:400],
                "similarity": c["similarity"],
            }
            for c in chunks
        ]
        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

        if not chunks:
            yield f"data: {json.dumps({'token': 'No relevant documents found.'})}\n\n"
            yield f"event: done\ndata: {json.dumps({'full_answer': 'No relevant documents found.'})}\n\n"
            return

        # 2. Stream answer tokens
        context = build_context(chunks)
        user_message = f"Source documents:\n\n{context}\n\n---\n\nQuestion: {body.question}"

        stream = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1000,
            stream=True,     # KEY: stream=True
        )

        full_answer = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                full_answer += token
                yield f"data: {json.dumps({'token': token})}\n\n"

        # 3. Signal completion
        yield f"event: done\ndata: {json.dumps({'full_answer': full_answer})}\n\n"

        # 4. Save to DB after streaming completes
        q = Question(
            company_id=company.id,
            question=body.question,
            answer=full_answer,
            sources=sources,
            doc_type_filter=body.doc_type,
        )
        db.add(q)
        db.commit()
        logger.info(f"Streamed answer saved for {ticker}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )