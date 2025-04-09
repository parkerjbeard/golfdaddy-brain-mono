from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator, Optional
import time
from sqlalchemy.exc import OperationalError

from app.config.settings import settings

# Base class for SQLAlchemy models
Base = declarative_base()

# Global engine and session factory, initialized when connect() is called
engine = None
SessionLocal = None

def wait_for_db(max_retries: int = 5, retry_interval: int = 2):
    """Wait for database to be ready."""
    # Skip in testing mode
    if settings.testing_mode:
        return True
        
    for attempt in range(max_retries):
        try:
            # Try to create a test connection
            DATABASE_URL = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
            test_engine = create_engine(
                DATABASE_URL,
                connect_args={"connect_timeout": 1}
            )
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed. Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                raise Exception("Could not connect to database after multiple attempts")

def connect(force: bool = False) -> None:
    """
    Initialize database connection. Only call this when you need database access.
    
    Args:
        force: Force reconnection even if already connected
    """
    global engine, SessionLocal
    
    # Skip database connection in testing mode
    if settings.testing_mode:
        return
    
    if engine is not None and not force:
        return  # Already connected
        
    # Create database URL
    DATABASE_URL = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    
    # Wait for database to be ready
    wait_for_db()
    
    # Create engine with retry settings
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args={
            "connect_timeout": 10,
            "application_name": "golfdaddy"
        }
    )
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session_factory():
    """Get the session factory, connecting first if needed."""
    if settings.testing_mode:
        return None
        
    if SessionLocal is None:
        connect()
    return SessionLocal

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    if settings.testing_mode:
        # Return None in testing mode, the caller should handle this
        yield None
        return
        
    if SessionLocal is None:
        connect()
        
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()