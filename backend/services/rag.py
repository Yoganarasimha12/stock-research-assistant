import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a financial research assistant that answers questions about companies.

STRICT RULES:
1. Answer ONLY using information from the provided [Source N] excerpts
2. Always cite sources inline using [Source N] format after each claim
3. If the answer is not in the sources, say exactly: "I cannot find this in the provided documents"
4. Never invent or guess financial figures — only state numbers that appear in the sources
5. If sources show different figures across time periods, note the change explicitly
6. Be concise but complete"""


def build_context(chunks: list[dict]) -> str:
    """Format retrieved chunks as numbered sources for the LLM"""
    parts = []
    for c in chunks:
        date = str(c.get("filing_date", ""))[:10]
        parts.append(
            f"[Source {c['rank']}] ({c['doc_type']}, {date})\n{c['text']}"
        )
    return "\n\n---\n\n".join(parts)


def generate_answer(query: str, chunks: list[dict]) -> dict:
    """
    Generate a cited answer from retrieved chunks.
    Returns answer text + source metadata.
    """
    if not chunks:
        return {
            "answer": "No relevant documents found. Please ensure the company has been ingested first.",
            "sources": [],
            "model": None,
        }

    context = build_context(chunks)
    user_message = f"Source documents:\n\n{context}\n\n---\n\nQuestion: {query}"

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        answer = response.choices[0].message.content
        model_used = response.model

        logger.info(f"Generated answer using {model_used}, {len(answer)} chars")

        return {
            "answer": answer,
            "sources": [
                {
                    "rank": c["rank"],
                    "doc_type": c["doc_type"],
                    "date": str(c["filing_date"])[:10],
                    "url": c["source_url"],
                    "chunk_text": c["text"][:400],
                    "similarity": c["similarity"],
                }
                for c in chunks
            ],
            "model": model_used,
        }

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return {
            "answer": f"Generation failed: {str(e)}",
            "sources": [],
            "model": None,
        }