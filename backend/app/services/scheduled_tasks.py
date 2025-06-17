import asyncio
from datetime import datetime, timedelta, time
import logging
from typing import Dict, Any

from app.services.daily_commit_analysis_service import DailyCommitAnalysisService
from app.services.eod_reminder_service import EODReminderService
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ScheduledTaskService:
    """Service for managing scheduled tasks like midnight analysis and EOD reminders"""
    
    def __init__(self):
        self.daily_analysis_service = DailyCommitAnalysisService()
        self.eod_reminder_service = EODReminderService()
        self.running_tasks = set()
    
    async def start_all_tasks(self):
        """Start all scheduled tasks"""
        logger.info("Starting scheduled tasks...")
        
        # Start midnight analysis task
        if settings.ENABLE_DAILY_BATCH_ANALYSIS:
            task = asyncio.create_task(self._run_midnight_analysis())
            self.running_tasks.add(task)
            task.add_done_callback(self.running_tasks.discard)
        
        # Start EOD reminder task  
        if getattr(settings, 'SLACK_ENABLED', False) and settings.ENABLE_EOD_REMINDERS:
            task = asyncio.create_task(self._run_eod_reminders())
            self.running_tasks.add(task)
            task.add_done_callback(self.running_tasks.discard)
        
        logger.info(f"Started {len(self.running_tasks)} scheduled tasks")
    
    async def stop_all_tasks(self):
        """Stop all running scheduled tasks"""
        logger.info("Stopping scheduled tasks...")
        
        for task in self.running_tasks:
            task.cancel()
        
        # Wait for all tasks to complete cancellation
        await asyncio.gather(*self.running_tasks, return_exceptions=True)
        
        logger.info("All scheduled tasks stopped")
    
    async def _run_midnight_analysis(self):
        """Run daily commit analysis at midnight every day"""
        while True:
            try:
                # Calculate time until next midnight
                now = datetime.now()
                tomorrow = now + timedelta(days=1)
                midnight = datetime.combine(tomorrow.date(), time.min)
                seconds_until_midnight = (midnight - now).total_seconds()
                
                # Add 5 minutes buffer to ensure day has fully ended
                wait_seconds = seconds_until_midnight + 300  # 5 minutes after midnight
                
                logger.info(f"Next midnight analysis scheduled in {wait_seconds/3600:.1f} hours")
                
                # Wait until midnight
                await asyncio.sleep(wait_seconds)
                
                # Run the analysis
                logger.info("Starting midnight commit analysis...")
                try:
                    results = await self.daily_analysis_service.run_midnight_analysis()
                    logger.info(f"Midnight analysis completed: {results}")
                except Exception as e:
                    logger.error(f"Error in midnight analysis: {e}", exc_info=True)
                
            except asyncio.CancelledError:
                logger.info("Midnight analysis task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in midnight analysis loop: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(3600)  # 1 hour
    
    async def _run_eod_reminders(self):
        """Run EOD reminders at configured time every day"""
        while True:
            try:
                # Get reminder time from settings (default 5:30 PM)
                reminder_hour = getattr(settings, 'EOD_REMINDER_HOUR', 17)
                reminder_minute = getattr(settings, 'EOD_REMINDER_MINUTE', 30)
                
                # Calculate time until next reminder
                now = datetime.now()
                today_reminder = now.replace(hour=reminder_hour, minute=reminder_minute, second=0, microsecond=0)
                
                if now >= today_reminder:
                    # Already past today's reminder time, schedule for tomorrow
                    tomorrow = now + timedelta(days=1)
                    next_reminder = tomorrow.replace(hour=reminder_hour, minute=reminder_minute, second=0, microsecond=0)
                else:
                    next_reminder = today_reminder
                
                seconds_until_reminder = (next_reminder - now).total_seconds()
                
                logger.info(f"Next EOD reminder scheduled in {seconds_until_reminder/3600:.1f} hours")
                
                # Wait until reminder time
                await asyncio.sleep(seconds_until_reminder)
                
                # Skip weekends if configured
                if getattr(settings, 'SKIP_WEEKEND_REMINDERS', True) and next_reminder.weekday() >= 5:
                    logger.info("Skipping EOD reminder for weekend")
                    continue
                
                # Send reminders
                logger.info("Starting EOD reminder process...")
                try:
                    results = await self.eod_reminder_service.send_eod_reminders()
                    logger.info(f"EOD reminders sent: {results}")
                except Exception as e:
                    logger.error(f"Error sending EOD reminders: {e}", exc_info=True)
                
            except asyncio.CancelledError:
                logger.info("EOD reminder task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in EOD reminder loop: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(3600)  # 1 hour
    
    async def run_analysis_for_date(self, date: datetime) -> Dict[str, Any]:
        """
        Manually trigger analysis for a specific date.
        Useful for backfilling or testing.
        """
        try:
            logger.info(f"Running manual analysis for {date.date()}")
            
            # Get users who need analysis for this date
            users = await self.daily_analysis_service.repository.get_users_without_analysis(date.date())
            
            results = {"analyzed": 0, "failed": 0, "users": []}
            
            for user_id in users:
                try:
                    analysis = await self.daily_analysis_service.analyze_for_date(user_id, date.date())
                    if analysis:
                        results["analyzed"] += 1
                        results["users"].append({
                            "user_id": str(user_id),
                            "hours": float(analysis.total_estimated_hours)
                        })
                except Exception as e:
                    logger.error(f"Failed to analyze user {user_id}: {e}")
                    results["failed"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error in manual analysis: {e}", exc_info=True)
            raise


# Global instance for easy access
scheduled_tasks = ScheduledTaskService()


async def start_scheduled_tasks():
    """Start all scheduled tasks - call this on app startup"""
    await scheduled_tasks.start_all_tasks()


async def stop_scheduled_tasks():
    """Stop all scheduled tasks - call this on app shutdown"""
    await scheduled_tasks.stop_all_tasks()