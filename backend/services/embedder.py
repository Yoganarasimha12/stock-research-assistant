import os
import time
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Loads once when the server starts — stays in memory
# all-MiniLM-L6-v2 is small, fast, good quality for financial text
model = SentenceTransformer("all-MiniLM-L6-v2")

logger.info("✅ Sentence transformer model loaded")


def get_chroma_collection():
    """
    Get or create the Chroma collection.
    Tries HTTP client first (for Docker), falls back to local.
    """
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8001"))

    try:
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()
        logger.info("Connected to Chroma HTTP server")
    except Exception:
        logger.info("Using local Chroma persistent client")
        client = chromadb.PersistentClient(path="./chroma_db")

    return client.get_or_create_collection(
        name="stock_docs",
        metadata={"hnsw:space": "cosine"}
    )


def get_embedding(text: str) -> list[float]:
    """
    Get embedding vector for a piece of text.
    Runs locally — no API call, no cost, no rate limits.
    """
    text = text.replace("\n", " ").strip()
    text = text[:5000]  # safety truncation
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_and_store(chunks: list, db) -> int:
    """
    Embed a list of Chunk objects and store in:
    - Chroma (vector + metadata for retrieval)
    - PostgreSQL (text for citation display)

    Returns number of chunks stored.
    """
    from models import DocumentChunk

    if not chunks:
        return 0

    collection = get_chroma_collection()
    stored = 0
    batch_size = 50  # larger batch fine since it's local (no API limits)

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.text for c in batch]

        # Embed entire batch at once — sentence-transformers is fast locally
        try:
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False
            ).tolist()
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            continue

        ids = []
        embs = []
        docs = []
        metas = []
        db_chunks = []

        for chunk, embedding in zip(batch, embeddings):
            chroma_id = f"doc{chunk.doc_id}_chunk{chunk.chunk_index}"

            # Skip if already exists in Chroma
            existing = collection.get(ids=[chroma_id])
            if existing["ids"]:
                continue

            ids.append(chroma_id)
            embs.append(embedding)
            docs.append(chunk.text)
            metas.append({
                "doc_id": chunk.doc_id,
                "company_id": chunk.company_id,
                "doc_type": chunk.doc_type,
                "filing_date": str(chunk.filing_date) if chunk.filing_date else "",
                "source_url": chunk.source_url,
                "chunk_index": chunk.chunk_index,
                "word_count": chunk.word_count,
            })

            db_chunks.append(DocumentChunk(
                doc_id=chunk.doc_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                chroma_id=chroma_id,
            ))

        if ids:
            collection.add(
                ids=ids,
                embeddings=embs,
                documents=docs,
                metadatas=metas
            )
            db.add_all(db_chunks)
            db.commit()
            stored += len(ids)
            logger.info(f"Stored batch of {len(ids)} chunks (total: {stored})")

    return stored


def get_collection_stats() -> dict:
    """How many chunks are stored in Chroma"""
    try:
        collection = get_chroma_collection()
        return {
            "total_chunks": collection.count(),
            "collection_name": collection.name,
            "embedding_model": "all-MiniLM-L6-v2 (local)",
        }
    except Exception as e:
        return {"error": str(e)}