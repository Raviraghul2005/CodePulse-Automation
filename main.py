import os
import json
import logging
from datetime import date
from dotenv import load_dotenv

# Import our tracker and sender modules
from github_tracker import fetch_github_activity, get_target_date_and_tz
from leetcode_tracker import fetch_leetcode_activity
from email_sender import send_daily_email

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging to write to both a file and standard output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join("logs", "activity.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Path to local JSON streak history database
HISTORY_FILE = os.path.join("logs", "history.json")

def load_history() -> dict:
    """Loads coding history from local JSON database, or initializes a new one if it doesn't exist."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
                # Ensure the new max_streak key exists for backward compatibility
                if "streak_history" in data:
                    if "max_streak" not in data["streak_history"]:
                        data["streak_history"]["max_streak"] = data["streak_history"].get("combined_streak", 0)
                return data
        except json.JSONDecodeError:
            logger.warning(f"History file {HISTORY_FILE} was corrupted. Initializing new history.")
    
    return {
        "streak_history": {
            "combined_streak": 0,
            "max_streak": 0,
            "last_active_date": None
        },
        "daily_logs": {}
    }

def save_history(history_data: dict):
    """Saves the updated coding history to the local JSON database."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history_data, f, indent=4)
        logger.info(f"Updated history database saved to {HISTORY_FILE}")
    except Exception as e:
        logger.error(f"Failed to save history: {e}")

def update_combined_streak(history: dict, active_today: bool, target_date: date) -> tuple:
    """
    Computes and updates the combined coding streak.
    If the user has GitHub commits OR LeetCode submissions today, they are active.
    The streak increases if they were active yesterday and today, stays same if already
    marked today, and resets to 0 if there was a gap.
    Returns a tuple of (combined_streak, combined_max_streak).
    """
    streak_data = history["streak_history"]
    last_active_str = streak_data.get("last_active_date")
    current_streak = streak_data.get("combined_streak", 0)
    max_streak = streak_data.get("max_streak", 0)
    
    target_date_str = str(target_date)
    
    if active_today:
        if last_active_str:
            last_active = date.fromisoformat(last_active_str)
            delta = target_date - last_active
            
            if delta.days == 1:
                # Active consecutive days, increment streak
                current_streak += 1
                logger.info(f"Consecutive active day! Streak incremented to {current_streak}.")
            elif delta.days > 1:
                # Gap in activity, reset to 1
                current_streak = 1
                logger.info(f"Gap detected (last active: {last_active_str}). Streak reset to 1.")
            # If delta.days == 0, they already did activity today, do not increment again.
        else:
            # First activity ever
            current_streak = 1
            logger.info("First activity recorded. Streak set to 1.")
            
        streak_data["combined_streak"] = current_streak
        streak_data["last_active_date"] = target_date_str
    else:
        # Inactive today. Let's see if the streak is broken.
        # If the last active date is older than yesterday, then the streak has officially broken.
        if last_active_str:
            last_active = date.fromisoformat(last_active_str)
            delta = target_date - last_active
            if delta.days > 1:
                current_streak = 0
                streak_data["combined_streak"] = 0
                logger.info("Streak officially broken due to inactivity.")
        else:
            current_streak = 0
            streak_data["combined_streak"] = 0

    # Calculate and update combined max streak
    if current_streak > max_streak:
        max_streak = current_streak
        streak_data["max_streak"] = max_streak
        logger.info(f"New personal best! Max combined streak updated to {max_streak}.")

    return current_streak, max_streak

def run_tracking_cycle() -> bool:
    """
    Orchestrates the full flow:
    1. Loads config
    2. Fetches GitHub and LeetCode activity
    3. Updates history database & streak
    4. Sends daily email summary
    """
    logger.info("--- Starting Daily Coding Tracking Cycle ---")
    
    # Reload environment variables to pick up any changes
    load_dotenv()
    
    github_user = os.getenv("GITHUB_USERNAME")
    leetcode_user = os.getenv("LEETCODE_USERNAME")
    
    if not github_user and not leetcode_user:
        logger.error("No usernames configured in environment. Please set GITHUB_USERNAME and/or LEETCODE_USERNAME in your .env file.")
        return False
        
    target_date, target_tz = get_target_date_and_tz()
    
    # 1. Fetch GitHub Activity
    logger.info(f"Fetching GitHub activity for '{github_user}'...")
    github_stats = fetch_github_activity(github_user)
    
    # 2. Fetch LeetCode Stats
    logger.info(f"Fetching LeetCode activity for '{leetcode_user}'...")
    leetcode_stats = fetch_leetcode_activity(leetcode_user)
    
    # 3. Process activity status
    gh_commits = github_stats.get("commits_today", 0) if github_stats.get("success") else 0
    lc_subs = leetcode_stats.get("submissions_today", 0) if leetcode_stats.get("success") else 0
    
    active_today = (gh_commits > 0) or (lc_subs > 0)
    logger.info(f"Activity check today: GitHub Commits = {gh_commits}, LeetCode Submissions = {lc_subs}. Active = {active_today}")
    
    # 4. Update History and Combined Streak
    history = load_history()
    combined_streak, combined_max_streak = update_combined_streak(history, active_today, target_date)
    
    # Record today's entry in history logs
    target_date_str = str(target_date)
    history["daily_logs"][target_date_str] = {
        "active": active_today,
        "github_commits": gh_commits,
        "leetcode_submissions": lc_subs,
        "leetcode_solved_total": leetcode_stats.get("total_solved", 0) if leetcode_stats.get("success") else 0
    }
    save_history(history)
    
    # Add combined streak info to stats dictionaries for email template consumption
    github_stats["combined_streak"] = combined_streak
    github_stats["combined_max_streak"] = combined_max_streak
    leetcode_stats["combined_streak"] = combined_streak
    leetcode_stats["combined_max_streak"] = combined_max_streak
    
    # 5. Send Summary Email
    logger.info("Assembling and sending summary email...")
    email_success = send_daily_email(github_stats, leetcode_stats)
    
    if email_success:
        logger.info("--- Tracking Cycle Successfully Completed ---")
        return True
    else:
        logger.error("--- Tracking Cycle Completed with Email Failure ---")
        return False

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    # Force loading of environment variables for standalone run
    load_dotenv()
    run_tracking_cycle()
