import asyncio
import logging

from app.services.scheduled_tasks import ScheduledTaskService

logger = logging.getLogger(__name__)


async def main() -> None:
    service = ScheduledTaskService()
    logger.info("Starting one-off daily analysis run")
    results = await service.daily_analysis_service.run_midnight_analysis()
    logger.info(f"Daily analysis completed: {results}")


if __name__ == "__main__":
    asyncio.run(main())
