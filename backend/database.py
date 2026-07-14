from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()  # reads your .env file

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost/stockresearch"
)

# Engine = the actual connection to PostgreSQL
engine = create_engine(DATABASE_URL)

# SessionLocal = factory that creates DB sessions
SessionLocal = sessionmaker(bind=engine)

# Base = parent class all your models will inherit from
Base = declarative_base()

def get_db():
    """
    Creates a DB session, hands it to the endpoint,
    then closes it automatically when the request is done.
    FastAPI calls this automatically via Depends()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Creates all tables in PostgreSQL if they don't exist yet"""
    Base.metadata.create_all(bind=engine)

def test_connection():
    """Quick check that DB is reachable"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connected:", result.fetchone())