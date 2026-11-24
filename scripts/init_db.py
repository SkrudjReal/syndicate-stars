"""Создаёт все таблицы из моделей если их нет."""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    from bot.database.engine import engine
    from bot.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info('Tables ensured (create_all)')

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
