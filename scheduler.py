import os
import time
import logging
import schedule
from dotenv import load_dotenv
from main import run_tracking_cycle

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

def start_scheduler():
    """Starts the persistent scheduler daemon for local execution."""
    load_dotenv()
    
    # Configure the schedule time from .env, default to 8:00 PM (20:00)
    scheduled_time = os.getenv("SCHEDULE_TIME", "20:00")
    
    logger.info("==============================================")
    logger.info("Starting Coding Consistency Scheduler Daemon")
    logger.info(f"Target run time: {scheduled_time} daily")
    logger.info("==============================================")
    
    # Schedule the tracking task daily
    schedule.every().day.at(scheduled_time).do(run_tracking_cycle)
    
    logger.info(f"Successfully scheduled. Waiting for run time at {scheduled_time}...")
    
    try:
        while True:
            # Check if any scheduled jobs are pending to run
            schedule.run_pending()
            # Sleep for 10 seconds to avoid high CPU usage
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("\nScheduler daemon stopped by user (Ctrl+C). Exiting gracefully.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the scheduler: {e}")

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    start_scheduler()
