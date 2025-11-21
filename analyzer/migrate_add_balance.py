"""
Migration script to add account_balance column to existing database.

This script safely adds the account_balance column to the scored_traders table
for existing databases that don't have it yet.
"""

import asyncio
import aiosqlite
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_database(db_path: str):
    """
    Add account_balance column to scored_traders table.

    Args:
        db_path: Path to the database file
    """
    db_file = Path(db_path)

    if not db_file.exists():
        logger.error(f"Database not found at {db_path}")
        return False

    logger.info(f"Migrating database: {db_path}")

    async with aiosqlite.connect(db_path) as db:
        # Check if column already exists
        async with db.execute("PRAGMA table_info(scored_traders)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'account_balance' in column_names:
                logger.info("Column 'account_balance' already exists. No migration needed.")
                return True

        # Add the column
        logger.info("Adding 'account_balance' column...")
        try:
            await db.execute("""
                ALTER TABLE scored_traders
                ADD COLUMN account_balance REAL
            """)
            await db.commit()
            logger.info("✓ Successfully added 'account_balance' column")
            return True
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            return False


async def main():
    """Run migration on default database paths."""
    # Default paths
    data_path = Path(__file__).parent / "data" / "analyzed_traders.db"
    config_path = Path(__file__).parent / "config" / "data" / "analyzed_traders.db"

    paths_to_migrate = []

    if data_path.exists():
        paths_to_migrate.append(str(data_path))

    if config_path.exists():
        paths_to_migrate.append(str(config_path))

    if not paths_to_migrate:
        logger.warning("No databases found to migrate")
        return

    for db_path in paths_to_migrate:
        success = await migrate_database(db_path)
        if success:
            logger.info(f"✓ Migration completed for {db_path}")
        else:
            logger.error(f"✗ Migration failed for {db_path}")


if __name__ == "__main__":
    asyncio.run(main())
