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
                # Ensure the new keys exist for backward compatibility
                if "streak_history" in data:
                    sh = data["streak_history"]
                    if "max_streak" not in sh:
                        sh["max_streak"] = sh.get("combined_streak", 0)
                    sh.setdefault("github_streak", 0)
                    sh.setdefault("github_max_streak", 0)
                    sh.setdefault("github_last_active_date", None)
                    sh.setdefault("leetcode_streak", 0)
                    sh.setdefault("leetcode_max_streak", 0)
                    sh.setdefault("leetcode_last_active_date", None)
                return data
        except json.JSONDecodeError:
            logger.warning(f"History file {HISTORY_FILE} was corrupted. Initializing new history.")
    
    return {
        "streak_history": {
            "combined_streak": 0,
            "max_streak": 0,
            "last_active_date": None,
            "github_streak": 0,
            "github_max_streak": 0,
            "github_last_active_date": None,
            "leetcode_streak": 0,
            "leetcode_max_streak": 0,
            "leetcode_last_active_date": None
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

def calculate_streak(daily_logs: dict, target_date: date, activity_type: str) -> tuple:
    """
    Calculates the current streak and max streak for a specific activity type.
    activity_type can be: 'github', 'leetcode', or 'combined'.
    """
    from datetime import timedelta
    # 1. Gather all activity dates
    active_dates = set()
    for date_str, log in daily_logs.items():
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            continue
            
        is_active = False
        if activity_type == "github":
            is_active = log.get("github_commits", 0) > 0
        elif activity_type == "leetcode":
            is_active = log.get("leetcode_submissions", 0) > 0
        elif activity_type == "combined":
            is_active = log.get("active", False)
            
        if is_active:
            active_dates.add(d)
            
    if not active_dates:
        return 0, 0
        
    # 2. Compute max streak by sorting dates and finding consecutive ranges
    sorted_dates = sorted(list(active_dates))
    
    max_streak = 0
    current_range_streak = 0
    prev_date = None
    
    for d in sorted_dates:
        if prev_date is None:
            current_range_streak = 1
        elif (d - prev_date).days == 1:
            current_range_streak += 1
        else:
            current_range_streak = 1
        
        if current_range_streak > max_streak:
            max_streak = current_range_streak
        prev_date = d
        
    # 3. Compute current streak relative to target_date
    current_streak = 0
    if target_date in active_dates:
        # User is active today. Traverse backwards.
        current_streak = 1
        check_date = target_date - timedelta(days=1)
        while check_date in active_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
    elif (target_date - timedelta(days=1)) in active_dates:
        # User is inactive today, but was active yesterday.
        current_streak = 1
        check_date = target_date - timedelta(days=2)
        while check_date in active_dates:
            current_streak += 1
            check_date -= timedelta(days=1)
    else:
        # Inactive today and yesterday
        current_streak = 0
        
    return current_streak, max(max_streak, current_streak)

def run_tracking_cycle() -> bool:
    """
    Orchestrates the full flow:
    1. Loads config
    2. Fetches GitHub and LeetCode activity
    3. Backfills the last 7 calendar days of activity & updates history database
    4. Calculates streaks (Combined, GitHub, LeetCode)
    5. Sends daily email summary
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
    
    # 1. Fetch GitHub Activity for Today
    logger.info(f"Fetching GitHub activity for '{github_user}'...")
    github_stats = fetch_github_activity(github_user)
    
    # 2. Fetch LeetCode Stats
    logger.info(f"Fetching LeetCode activity for '{leetcode_user}'...")
    leetcode_stats = fetch_leetcode_activity(leetcode_user)
    
    if not github_stats.get("success") and not leetcode_stats.get("success"):
        logger.error("Both GitHub and LeetCode fetches failed. Aborting cycle.")
        return False

    # 3. Backfill last 7 calendar days of activity in history logs
    history = load_history()
    from datetime import timedelta
    last_7_dates = [target_date - timedelta(days=i) for i in range(6, -1, -1)]
    
    # Fetch GitHub commits history for the last 7 days
    from github_tracker import fetch_github_commits_history
    history_commits = fetch_github_commits_history(github_user, last_7_dates[0], last_7_dates[-1], target_tz)
    
    # Fetch LeetCode submissions by date
    leetcode_subs_by_date = leetcode_stats.get("submissions_by_date", {})
    
    # Backfill all LeetCode historical submissions into daily_logs
    for date_str, subs in leetcode_subs_by_date.items():
        if date_str not in history["daily_logs"]:
            history["daily_logs"][date_str] = {
                "active": subs > 0,
                "github_commits": 0,
                "leetcode_submissions": subs,
                "leetcode_solved_total": 0
            }
        else:
            history["daily_logs"][date_str]["leetcode_submissions"] = max(
                history["daily_logs"][date_str].get("leetcode_submissions", 0), subs
            )
            history["daily_logs"][date_str]["active"] = (
                history["daily_logs"][date_str].get("github_commits", 0) > 0 or 
                history["daily_logs"][date_str]["leetcode_submissions"] > 0
            )
            
    for d in last_7_dates:
        date_str = str(d)
        existing_log = history["daily_logs"].get(date_str, {})
        
        # Determine GitHub commits count
        if d == target_date:
            gh_commits = github_stats.get("commits_today", 0) if github_stats.get("success") else 0
        else:
            existing_commits = existing_log.get("github_commits", 0)
            fetched_commits = len(history_commits[date_str]) if date_str in history_commits else 0
            gh_commits = max(existing_commits, fetched_commits)
            
        # Determine LeetCode submissions count
        if d == target_date:
            lc_subs = leetcode_stats.get("submissions_today", 0) if leetcode_stats.get("success") else 0
        else:
            existing_subs = existing_log.get("leetcode_submissions", 0)
            fetched_subs = leetcode_subs_by_date.get(date_str, 0)
            lc_subs = max(existing_subs, fetched_subs)
            
        active = (gh_commits > 0) or (lc_subs > 0)
        
        # Populate daily log entry
        history["daily_logs"][date_str] = {
            "active": active,
            "github_commits": gh_commits,
            "leetcode_submissions": lc_subs,
            "leetcode_solved_total": leetcode_stats.get("total_solved", 0) if (d == target_date and leetcode_stats.get("success")) else existing_log.get("leetcode_solved_total", 0)
        }
        
    # Calculate streaks dynamically
    combined_streak, combined_max = calculate_streak(history["daily_logs"], target_date, "combined")
    github_streak, github_max = calculate_streak(history["daily_logs"], target_date, "github")
    leetcode_streak, leetcode_max = calculate_streak(history["daily_logs"], target_date, "leetcode")
    
    final_lc_streak = leetcode_streak
    
    # Update streak history data
    sh = history["streak_history"]
    sh["combined_streak"] = combined_streak
    sh["max_streak"] = combined_max  # Keep old key for backward compatibility
    sh["last_active_date"] = str(target_date)  # Keep old key
    
    sh["github_streak"] = github_streak
    sh["github_max_streak"] = github_max
    if github_streak > 0:
        sh["github_last_active_date"] = str(target_date)
        
    sh["leetcode_streak"] = final_lc_streak
    sh["leetcode_max_streak"] = max(sh.get("leetcode_max_streak", 0), leetcode_max, final_lc_streak)
    if final_lc_streak > 0:
        sh["leetcode_last_active_date"] = str(target_date)
        
    save_history(history)
    
    # Add streak info to stats dictionaries for email template consumption
    github_stats["combined_streak"] = combined_streak
    github_stats["combined_max_streak"] = combined_max
    github_stats["github_streak"] = github_streak
    github_stats["github_max_streak"] = github_max
    github_stats["leetcode_streak"] = final_lc_streak
    github_stats["leetcode_max_streak"] = sh["leetcode_max_streak"]
    
    leetcode_stats["combined_streak"] = combined_streak
    leetcode_stats["combined_max_streak"] = combined_max
    leetcode_stats["github_streak"] = github_streak
    leetcode_stats["github_max_streak"] = github_max
    leetcode_stats["current_streak"] = final_lc_streak
    leetcode_stats["leetcode_max_streak"] = sh["leetcode_max_streak"]
    
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
