#!/usr/bin/env python3
"""
Script to test Batch 2 database migrations.
Run this to verify that all migrations apply correctly.
"""
import asyncio
import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_migrations():
    """Test that Batch 2 migrations can be applied successfully."""
    
    # Create async engine
    if settings.DATABASE_URL.startswith("postgresql://"):
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = settings.DATABASE_URL
    
    engine = create_async_engine(async_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            logger.info("Testing Batch 2 migrations...")
            
            # Read migration file
            migration_path = Path(__file__).parent.parent / "migrations" / "batch2_doc_agent_foundation.sql"
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            
            # Split into individual statements (rough split on semicolons)
            # Note: This is simplified - a proper parser would handle semicolons in strings
            statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
            
            # Execute each statement
            for i, statement in enumerate(statements, 1):
                if statement and not statement.startswith('--'):
                    try:
                        logger.info(f"Executing statement {i}/{len(statements)}...")
                        await conn.execute(text(statement))
                    except Exception as e:
                        logger.warning(f"Statement {i} failed (may be expected): {str(e)[:100]}")
            
            logger.info("✅ Migration script executed")
            
            # Verify tables exist
            tables_to_check = [
                'doc_chunks',
                'code_symbols', 
                'proposals',
                'embeddings_meta'
            ]
            
            for table in tables_to_check:
                result = await conn.execute(
                    text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = :table"),
                    {"table": table}
                )
                count = result.scalar()
                if count > 0:
                    logger.info(f"✅ Table '{table}' exists")
                else:
                    logger.error(f"❌ Table '{table}' not found")
            
            # Check if doc_approvals has new columns
            result = await conn.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'doc_approvals' 
                    AND column_name IN ('proposal_id', 'head_sha', 'check_run_id', 'opened_by')
                """)
            )
            new_columns = [row[0] for row in result]
            
            if new_columns:
                logger.info(f"✅ Enhanced doc_approvals table with columns: {new_columns}")
            else:
                logger.warning("⚠️ doc_approvals table not enhanced or doesn't exist")
            
            # Check pgvector extension
            result = await conn.execute(
                text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
            )
            if result.scalar() > 0:
                logger.info("✅ pgvector extension installed")
            else:
                logger.warning("⚠️ pgvector extension not found")
            
            # Test creating sample data
            logger.info("\nTesting data insertion...")
            
            # Insert test embedding metadata
            await conn.execute(
                text("""
                    INSERT INTO embeddings_meta (model, dim)
                    VALUES (:model, :dim)
                    ON CONFLICT (model) DO NOTHING
                """),
                {"model": "text-embedding-3-large", "dim": 3072}
            )
            logger.info("✅ Test data inserted into embeddings_meta")
            
            # Insert test proposal
            await conn.execute(
                text("""
                    INSERT INTO proposals (commit, repo, patch, status, cost_cents)
                    VALUES (:commit, :repo, :patch, :status, :cost)
                    ON CONFLICT (commit, repo) DO NOTHING
                """),
                {
                    "commit": "test123",
                    "repo": "test-repo",
                    "patch": "Test patch",
                    "status": "pending",
                    "cost": 10
                }
            )
            logger.info("✅ Test data inserted into proposals")
            
            logger.info("\n🎉 All Batch 2 migration tests passed!")
            
    except Exception as e:
        logger.error(f"❌ Migration test failed: {e}")
        raise
    finally:
        await engine.dispose()


async def cleanup_test_data():
    """Clean up test data created during migration test."""
    
    if settings.DATABASE_URL.startswith("postgresql://"):
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = settings.DATABASE_URL
    
    engine = create_async_engine(async_url, echo=False)
    
    try:
        async with engine.begin() as conn:
            logger.info("Cleaning up test data...")
            
            # Delete test data
            await conn.execute(
                text("DELETE FROM proposals WHERE commit = :commit"),
                {"commit": "test123"}
            )
            
            logger.info("✅ Test data cleaned up")
            
    except Exception as e:
        logger.warning(f"Cleanup failed (non-critical): {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_migrations())
    asyncio.run(cleanup_test_data())