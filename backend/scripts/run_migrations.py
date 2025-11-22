#!/usr/bin/env python3
"""
Database migration runner script.
Handles both SQL and Alembic migrations.
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import List, Optional
import asyncpg
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations."""
    
    def __init__(self, database_url: str):
        # Handle SQLAlchemy-style DSNs
        self.database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        self.migrations_dir = Path(__file__).parent.parent / "migrations"
        
    async def create_migrations_table(self, conn: asyncpg.Connection):
        """Create migrations tracking table if it doesn't exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time FLOAT,
                checksum VARCHAR(64),
                description TEXT
            )
        """)
        
    async def get_applied_migrations(self, conn: asyncpg.Connection) -> List[str]:
        """Get list of already applied migrations."""
        rows = await conn.fetch(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        return [row['version'] for row in rows]
        
    async def get_pending_migrations(self, conn: asyncpg.Connection) -> List[Path]:
        """Get list of pending migration files."""
        applied = await self.get_applied_migrations(conn)
        
        migration_files = []
        sql_files = sorted(self.migrations_dir.glob("*.sql"))
        
        for file in sql_files:
            # Skip rollback files
            if "rollback" in file.name or "down" in file.name:
                continue
                
            version = file.stem
            if version not in applied:
                migration_files.append(file)
                
        return migration_files
        
    async def calculate_checksum(self, content: str) -> str:
        """Calculate checksum for migration content."""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
        
    async def apply_migration(
        self, 
        conn: asyncpg.Connection, 
        migration_file: Path
    ) -> Optional[float]:
        """Apply a single migration file."""
        version = migration_file.stem
        
        logger.info(f"Applying migration: {version}")
        
        try:
            # Read migration content
            content = migration_file.read_text()
            checksum = await self.calculate_checksum(content)
            
            # Start transaction
            async with conn.transaction():
                start_time = datetime.now()
                
                # Execute migration
                await conn.execute(content)
                
                # Record migration
                execution_time = (datetime.now() - start_time).total_seconds()
                await conn.execute("""
                    INSERT INTO schema_migrations (version, execution_time, checksum, description)
                    VALUES ($1, $2, $3, $4)
                """, version, execution_time, checksum, f"Migration from {migration_file.name}")
                
                logger.info(f"✅ Migration {version} applied successfully ({execution_time:.2f}s)")
                return execution_time
                
        except Exception as e:
            logger.error(f"❌ Failed to apply migration {version}: {e}")
            raise
            
    async def run_migrations(self) -> int:
        """Run all pending migrations."""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Create migrations table
            await self.create_migrations_table(conn)
            
            # Get pending migrations
            pending = await self.get_pending_migrations(conn)
            
            if not pending:
                logger.info("No pending migrations")
                return 0
                
            logger.info(f"Found {len(pending)} pending migrations")
            
            # Apply migrations
            total_time = 0.0
            for migration_file in pending:
                execution_time = await self.apply_migration(conn, migration_file)
                if execution_time:
                    total_time += execution_time
                    
            logger.info(f"✅ All migrations completed successfully (Total time: {total_time:.2f}s)")
            return len(pending)
            
        finally:
            await conn.close()
            
    async def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration."""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Check if migration exists
            row = await conn.fetchrow(
                "SELECT * FROM schema_migrations WHERE version = $1", 
                version
            )
            
            if not row:
                logger.error(f"Migration {version} not found")
                return False
                
            # Look for rollback file
            rollback_file = self.migrations_dir / f"{version}_rollback.sql"
            if not rollback_file.exists():
                logger.error(f"Rollback file not found: {rollback_file}")
                return False
                
            logger.info(f"Rolling back migration: {version}")
            
            # Execute rollback
            async with conn.transaction():
                content = rollback_file.read_text()
                await conn.execute(content)
                
                # Remove migration record
                await conn.execute(
                    "DELETE FROM schema_migrations WHERE version = $1",
                    version
                )
                
            logger.info(f"✅ Migration {version} rolled back successfully")
            return True
            
        finally:
            await conn.close()
            
    async def check_migrations_status(self) -> dict:
        """Check the current migration status."""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            await self.create_migrations_table(conn)
            
            applied = await self.get_applied_migrations(conn)
            pending = await self.get_pending_migrations(conn)
            
            return {
                "applied_count": len(applied),
                "pending_count": len(pending),
                "latest_applied": applied[-1] if applied else None,
                "pending_migrations": [f.stem for f in pending]
            }
            
        finally:
            await conn.close()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database migration tool")
    parser.add_argument(
        "command",
        choices=["migrate", "rollback", "status"],
        help="Command to execute"
    )
    parser.add_argument(
        "--version",
        help="Migration version (for rollback)"
    )
    parser.add_argument(
        "--database-url",
        default=settings.DATABASE_URL,
        help="Database URL"
    )
    
    args = parser.parse_args()
    
    runner = MigrationRunner(args.database_url)
    
    if args.command == "migrate":
        count = await runner.run_migrations()
        sys.exit(0 if count >= 0 else 1)
        
    elif args.command == "rollback":
        if not args.version:
            logger.error("Version required for rollback")
            sys.exit(1)
            
        success = await runner.rollback_migration(args.version)
        sys.exit(0 if success else 1)
        
    elif args.command == "status":
        status = await runner.check_migrations_status()
        print(f"Applied migrations: {status['applied_count']}")
        print(f"Pending migrations: {status['pending_count']}")
        if status['latest_applied']:
            print(f"Latest applied: {status['latest_applied']}")
        if status['pending_migrations']:
            print("Pending:")
            for migration in status['pending_migrations']:
                print(f"  - {migration}")
                
        # Exit with code 1 if there are pending migrations
        sys.exit(1 if status['pending_count'] > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())