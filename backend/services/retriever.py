import math
import logging
from datetime import datetime
from services.embedder import get_embedding, get_chroma_collection

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    company_id: int,
    n_results: int = 6,
    doc_type_filter: str = None,
    use_recency_boost: bool = True,
) -> list[dict]:
    """
    Find the most relevant document chunks for a query.

    Args:
        query: the user's question
        company_id: only search chunks from this company
        n_results: how many chunks to return
        doc_type_filter: "10-K", "10-Q", "news" or None for all
        use_recency_boost: give slight preference to recent filings

    Returns:
        List of chunk dicts with text, metadata, and similarity scores
    """
    collection = get_chroma_collection()

    # Check if collection has any data
    if collection.count() == 0:
        logger.warning("Chroma collection is empty — has ingestion run?")
        return []

    # Embed the question
    query_embedding = get_embedding(query)

    # Build metadata filter — CRITICAL: always filter by company
    if doc_type_filter and doc_type_filter != "all":
        where = {
            "$and": [
                {"company_id": {"$eq": company_id}},
                {"doc_type": {"$eq": doc_type_filter}}
            ]
        }
    else:
        where = {"company_id": {"$eq": company_id}}

    # Fetch more than needed so we can re-rank and deduplicate
    fetch_n = min(n_results * 3, collection.count())

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"Chroma query failed: {e}")
        return []

    # Build chunk list with scores
    chunks = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Convert cosine distance to similarity (1 = identical, 0 = unrelated)
        similarity = 1 - distance

        # Recency boost — recent docs score slightly higher
        boost = 0.0
        if use_recency_boost and meta.get("filing_date"):
            try:
                filing_date = datetime.fromisoformat(
                    str(meta["filing_date"]).split(" ")[0]
                )
                days_ago = (datetime.utcnow() - filing_date).days
                # Exponential decay: today = 0.05 boost, 1 year ago = ~0.02, 2 years = ~0.007
                boost = math.exp(-days_ago / 365) * 0.05
            except Exception:
                pass

        chunks.append({
            "text": doc,
            "doc_type": meta.get("doc_type", ""),
            "filing_date": meta.get("filing_date", ""),
            "source_url": meta.get("source_url", ""),
            "doc_id": meta.get("doc_id"),
            "chunk_index": meta.get("chunk_index"),
            "similarity": round(similarity, 4),
            "final_score": round(similarity + boost, 4),
        })

    # Sort by final score (similarity + recency boost)
    chunks.sort(key=lambda x: x["final_score"], reverse=True)

    # Remove low quality chunks — below 0.3 similarity is usually noise
    chunks = [c for c in chunks if c["similarity"] > 0.3]

    # Deduplicate — remove near-identical chunks
    seen_texts = set()
    unique_chunks = []
    for chunk in chunks:
        # Use first 100 chars as fingerprint
        text_key = chunk["text"][:100].strip()
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique_chunks.append(chunk)
        if len(unique_chunks) >= n_results:
            break

    # Add rank number after deduplication
    for i, chunk in enumerate(unique_chunks):
        chunk["rank"] = i + 1

    logger.info(
        f"Retrieved {len(unique_chunks)} chunks for query '{query[:50]}...' "
        f"(company_id={company_id}, filter={doc_type_filter})"
    )

    return unique_chunks