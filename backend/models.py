from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    ingestion_status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    # One company has many documents
    documents = relationship("Document", back_populates="company")
    questions = relationship("Question", back_populates="company")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    doc_type = Column(String(20))      # "10-K", "10-Q", "news"
    title = Column(String(500))
    source_url = Column(String(1000))
    raw_text = Column(Text)
    filing_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer)
    text = Column(Text)
    chroma_id = Column(String(200), unique=True)

    document = relationship("Document", back_populates="chunks")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    question = Column(Text)
    answer = Column(Text)
    sources = Column(JSON)
    doc_type_filter = Column(String(20))
    asked_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="questions")