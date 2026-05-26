import os
import json
import requests
import logging
from datetime import datetime, timezone, timedelta
from github_tracker import get_target_date_and_tz

# Set up logging
logger = logging.getLogger(__name__)

def fetch_leetcode_activity(username: str) -> dict:
    """
    Fetches the LeetCode activity and stats for a given username.
    Returns a dictionary of stats.
    """
    stats = {
        "success": False,
        "username": username,
        "total_solved": 0,
        "easy_solved": 0,
        "medium_solved": 0,
        "hard_solved": 0,
        "submissions_today": 0,
        "submissions_by_date": {},
        "current_streak": 0,
        "max_streak": 0,
        "error": None
    }
    
    if not username:
        stats["error"] = "LeetCode username is not configured."
        logger.error(stats["error"])
        return stats

    # Get target date and timezone
    target_date, target_tz = get_target_date_and_tz()
    logger.info(f"Tracking LeetCode activity for username: {username} on date: {target_date}")

    url = "https://leetcode.com/graphql"
    
    # GraphQL query to get user details, submission counts and submission calendar
    query = """
    query userStats($username: String!) {
      matchedUser(username: $username) {
        username
        submitStats {
          acSubmissionNum {
            difficulty
            count
            submissions
          }
        }
        userCalendar {
          streak
          submissionCalendar
        }
      }
    }
    """
    
    payload = {
        "query": query,
        "variables": {"username": username}
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if GraphQL returned errors
        if "errors" in data:
            errors = data["errors"]
            error_msg = errors[0].get("message", "Unknown GraphQL error")
            stats["error"] = f"LeetCode GraphQL Error: {error_msg}"
            logger.error(stats["error"])
            return stats
            
        user_data = data.get("data", {}).get("matchedUser")
        
        if not user_data:
            stats["error"] = f"LeetCode user '{username}' not found."
            logger.error(stats["error"])
            return stats
            
        # Parse problems solved by difficulty
        submit_stats = user_data.get("submitStats", {})
        ac_submissions = submit_stats.get("acSubmissionNum", [])
        
        for item in ac_submissions:
            difficulty = item.get("difficulty")
            count = item.get("count", 0)
            
            if difficulty == "All":
                stats["total_solved"] = count
            elif difficulty == "Easy":
                stats["easy_solved"] = count
            elif difficulty == "Medium":
                stats["medium_solved"] = count
            elif difficulty == "Hard":
                stats["hard_solved"] = count
                
        # Parse user calendar and submissions today
        calendar_data = user_data.get("userCalendar") or {}
        stats["current_streak"] = calendar_data.get("streak", 0)
        
        submission_calendar_str = calendar_data.get("submissionCalendar", "{}")
        
        # Calculate submissions today
        submissions_today = 0
        submissions_by_date = {}
        try:
            # submissionCalendar is a JSON string mapping Unix timestamp strings to counts
            # e.g., '{"1716681600": 3}'
            submission_calendar = json.loads(submission_calendar_str)
            
            # Today's date in UTC (since LeetCode's submission calendar timestamps are UTC midnight)
            utc_today = datetime.now(timezone.utc).date()
            
            for ts_str, count in submission_calendar.items():
                ts = int(ts_str)
                # Convert the Unix timestamp (at midnight UTC) to a UTC date
                dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
                # Also convert to the local target timezone
                dt_local = dt_utc.astimezone(target_tz)
                
                local_date_str = str(dt_local.date())
                submissions_by_date[local_date_str] = submissions_by_date.get(local_date_str, 0) + count
                
                # Check if it matches today in the target timezone or today in UTC
                if dt_local.date() == target_date or dt_utc.date() == utc_today:
                    submissions_today += count
                    
            stats["submissions_today"] = submissions_today
            stats["submissions_by_date"] = submissions_by_date
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Error parsing submission calendar JSON: {e}")
            stats["submissions_today"] = 0
            stats["submissions_by_date"] = {}
            
        stats["success"] = True
        logger.info(f"LeetCode fetch successful. Solved: {stats['total_solved']} (E:{stats['easy_solved']}, M:{stats['medium_solved']}, H:{stats['hard_solved']}), Today: {stats['submissions_today']} subs, Streak: {stats['current_streak']}")
        
    except requests.exceptions.RequestException as e:
        stats["error"] = f"Network error connecting to LeetCode: {e}"
        logger.error(stats["error"])
    except Exception as e:
        stats["error"] = f"An unexpected error occurred parsing LeetCode data: {e}"
        logger.error(stats["error"])
        
    return stats

if __name__ == "__main__":
    # Test execution
    from dotenv import load_dotenv
    load_dotenv()
    test_user = os.getenv("LEETCODE_USERNAME", "alex")
    print(f"Testing LeetCode tracker for user '{test_user}':")
    result = fetch_leetcode_activity(test_user)
    import pprint
    pprint.pprint(result)
