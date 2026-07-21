import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """One chunk of text from a document"""
    text: str
    doc_id: int
    company_id: int
    doc_type: str
    filing_date: Optional[datetime]
    chunk_index: int
    source_url: str
    word_count: int


def clean_text(text: str) -> str:
    """Remove noise before chunking"""
    text = re.sub(r'\n{3,}', '\n\n', text)       # collapse excessive newlines
    text = re.sub(r'[ \t]{2,}', ' ', text)        # collapse spaces
    text = re.sub(r'[^\x20-\x7E\n]', '', text)   # remove non-ASCII characters
    return text.strip()


def chunk_by_sentences(text: str, max_words: int = 400) -> list[str]:
    """
    Split text into chunks at sentence boundaries.
    Best for: news articles, earnings transcripts
    """
    text = clean_text(text)

    # Split on sentence endings followed by capital letter
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

    chunks = []
    current = []
    current_count = 0

    for sentence in sentences:
        word_count = len(sentence.split())

        if current_count + word_count > max_words and current:
            # Save current chunk
            chunks.append(" ".join(current))
            # Keep last 3 sentences as overlap for next chunk
            current = current[-3:]
            current_count = len(" ".join(current).split())

        current.append(sentence)
        current_count += word_count

    # Don't forget the last chunk
    if current:
        chunks.append(" ".join(current))

    # Filter out tiny chunks (less than 30 words)
    return [c for c in chunks if len(c.split()) >= 30]


def chunk_by_sections(text: str, max_words: int = 500) -> list[str]:
    """
    Split SEC filings on ITEM headers first, then sub-chunk large sections.
    Best for: 10-K, 10-Q filings which have consistent section structure
    """
    # SEC filing section headers
    section_pattern = r'((?:ITEM|Item)\s+\d+[A-Za-z]?\.?\s+[A-Z][A-Z\s]+)'

    parts = re.split(section_pattern, text)
    chunks = []
    current_header = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this part is a section header
        if re.match(section_pattern, part):
            current_header = part
            continue

        # Combine header with content
        full_section = f"{current_header}\n{part}".strip() if current_header else part

        # Sub-chunk large sections
        if len(full_section.split()) > max_words:
            sub_chunks = chunk_by_sentences(full_section, max_words)
            chunks.extend(sub_chunks)
        elif len(full_section.split()) >= 30:
            chunks.append(full_section)

    # If section splitting found nothing, fall back to sentence chunking
    if not chunks:
        logger.warning("Section chunking found no sections, falling back to sentence chunking")
        chunks = chunk_by_sentences(text, max_words)

    return chunks


def chunk_document(doc) -> list[Chunk]:
    """
    Main entry point — picks the right chunking strategy
    based on document type.
    """
    if not doc.raw_text:
        logger.warning(f"Document {doc.id} has no text, skipping")
        return []

    # Pick strategy based on doc type
    if doc.doc_type in ("10-K", "10-Q"):
        text_chunks = chunk_by_sections(doc.raw_text)
    else:
        # News articles, earnings transcripts
        text_chunks = chunk_by_sentences(doc.raw_text)

    chunks = [
        Chunk(
            text=text,
            doc_id=doc.id,
            company_id=doc.company_id,
            doc_type=doc.doc_type,
            filing_date=doc.filing_date,
            chunk_index=i,
            source_url=doc.source_url or "",
            word_count=len(text.split()),
        )
        for i, text in enumerate(text_chunks)
    ]

    logger.info(
        f"Chunked doc {doc.id} ({doc.doc_type}) into "
        f"{len(chunks)} chunks, avg {sum(c.word_count for c in chunks) // max(len(chunks),1)} words"
    )
    return chunks