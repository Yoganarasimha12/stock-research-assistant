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
from fastapi import WebSocket, WebSocketDisconnect


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
    
@router.websocket("/{ticker}/ws")
async def websocket_qa(
    websocket: WebSocket,
    ticker: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for multi-turn conversation.
    Keeps conversation history so follow-up questions work.
    User sends: {"question": "...", "doc_type": "10-K"}
    Server sends: {"type": "sources", "sources": [...]}
                  {"type": "token", "token": "..."}
                  {"type": "done"}
    """
    await websocket.accept()

    company = db.query(Company).filter(
        Company.ticker == ticker.upper()
    ).first()

    if not company:
        await websocket.send_json({"type": "error", "message": "Company not found"})
        await websocket.close()
        return

    if company.ingestion_status != "done":
        await websocket.send_json({
            "type": "error",
            "message": f"Ingestion not complete. Status: {company.ingestion_status}"
        })
        await websocket.close()
        return

    # Conversation history — persists for the entire WebSocket session
    conversation_history = []
    logger.info(f"WebSocket connected for {ticker}")

    try:
        while True:
            # Wait for a question from the client
            data = await websocket.receive_json()
            question = data.get("question", "").strip()
            doc_type = data.get("doc_type")

            if not question:
                await websocket.send_json({
                    "type": "error",
                    "message": "Empty question received"
                })
                continue

            logger.info(f"WS question for {ticker}: '{question[:50]}'")

            # Retrieve relevant chunks
            chunks = retrieve(
                query=question,
                company_id=company.id,
                doc_type_filter=doc_type
            )

            # Send sources first
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
            await websocket.send_json({"type": "sources", "sources": sources})

            # Build messages with conversation history for multi-turn
            context = build_context(chunks)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            # Include last 3 Q&A pairs (6 messages) for context
            messages.extend(conversation_history[-6:])

            # Add current question with retrieved context
            messages.append({
                "role": "user",
                "content": f"Source documents:\n\n{context}\n\n---\n\nQuestion: {question}"
            })

            # Stream response tokens
            stream = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.1,
                max_tokens=1000,
                stream=True,
            )

            full_answer = ""
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_answer += token
                    await websocket.send_json({
                        "type": "token",
                        "token": token
                    })

            # Signal done
            await websocket.send_json({"type": "done"})

            # Update conversation history
            conversation_history.append({
                "role": "user",
                "content": question
            })
            conversation_history.append({
                "role": "assistant",
                "content": full_answer
            })

            # Save to DB
            q = Question(
                company_id=company.id,
                question=question,
                answer=full_answer,
                sources=sources,
                doc_type_filter=doc_type,
            )
            db.add(q)
            db.commit()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {ticker}")
    except Exception as e:
        logger.error(f"WebSocket error for {ticker}: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass