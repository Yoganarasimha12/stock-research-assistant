from database import SessionLocal
from models import Document
from services.chunker import chunk_document, chunk_by_sentences, chunk_by_sections

db = SessionLocal()

print("=== Testing Chunker ===\n")

# Test 1: Chunk a 10-K filing
doc_10k = db.query(Document).filter(Document.doc_type == "10-K").first()
if doc_10k:
    chunks = chunk_document(doc_10k)
    print(f"10-K: '{doc_10k.title}'")
    print(f"  Original words: {len(doc_10k.raw_text.split()):,}")
    print(f"  Chunks created: {len(chunks)}")
    print(f"  Avg chunk size: {sum(c.word_count for c in chunks) // len(chunks)} words")
    print(f"  Min chunk size: {min(c.word_count for c in chunks)} words")
    print(f"  Max chunk size: {max(c.word_count for c in chunks)} words")
    print(f"\n  Sample chunk 1:\n  {chunks[0].text[:300]}")
    print(f"\n  Sample chunk 5:\n  {chunks[4].text[:300] if len(chunks) > 4 else 'N/A'}")
    print()

# Test 2: Chunk a news article
doc_news = db.query(Document).filter(Document.doc_type == "news").first()
if doc_news:
    chunks = chunk_document(doc_news)
    print(f"News: '{doc_news.title}'")
    print(f"  Original words: {len(doc_news.raw_text.split()):,}")
    print(f"  Chunks created: {len(chunks)}")
    if chunks:
        print(f"  Sample chunk:\n  {chunks[0].text[:300]}")
    print()

# Test 3: Compare strategies side by side on same 10-K
if doc_10k:
    sentence_chunks = chunk_by_sentences(doc_10k.raw_text, max_words=400)
    section_chunks = chunk_by_sections(doc_10k.raw_text, max_words=500)
    print("=== Strategy Comparison (same 10-K) ===")
    print(f"  Sentence-based: {len(sentence_chunks)} chunks")
    print(f"  Section-based:  {len(section_chunks)} chunks")
    print(f"\n  Sentence chunk sample:\n  {sentence_chunks[0][:200]}")
    print(f"\n  Section chunk sample:\n  {section_chunks[0][:200]}")

db.close()