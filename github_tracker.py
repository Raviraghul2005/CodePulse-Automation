import os
import requests
import logging
from datetime import datetime, timezone, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_target_date_and_tz():
    """
    Returns the target date to track (today) and timezone timezone-aware object.
    Supports TIMEZONE_OFFSET in .env (e.g., TIMEZONE_OFFSET=5.5 for IST)
    to override server timezone when running on remote platforms (like GitHub Actions).
    """
    offset_env = os.getenv("TIMEZONE_OFFSET")
    if offset_env is not None:
        try:
            offset_hours = float(offset_env)
            tz = timezone(timedelta(hours=offset_hours))
            target_now = datetime.now(tz)
            logger.info(f"Using configured timezone offset: UTC{'+' if offset_hours >= 0 else ''}{offset_hours}")
            return target_now.date(), tz
        except ValueError:
            logger.warning(f"Invalid TIMEZONE_OFFSET: '{offset_env}'. Defaulting to system local timezone.")
    
    # Fallback to local system timezone
    target_now = datetime.now().astimezone()
    logger.info(f"Using system local timezone: {target_now.tzinfo}")
    return target_now.date(), target_now.tzinfo

def fetch_github_activity(username: str) -> dict:
    """
    Fetches the GitHub activity for a given username for 'today'.
    Returns a dictionary of stats.
    """
    # Prepare result structure
    stats = {
        "success": False,
        "username": username,
        "commits_today": 0,
        "repos_active": [],
        "total_events": 0,
        "error": None
    }
    
    if not username:
        stats["error"] = "GitHub username is not configured."
        logger.error(stats["error"])
        return stats

    # Get target date and timezone
    target_date, target_tz = get_target_date_and_tz()
    logger.info(f"Tracking GitHub activity for username: {username} on date: {target_date}")
    
    # Construct API URL for user events
    url = f"https://api.github.com/users/{username}/events"
    
    # Prepare headers
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CodingConsistencyTracker/1.0"
    }
    
    # Authenticated requests have higher rate limits. Use GITHUB_TOKEN if available.
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        logger.info("Using GITHUB_TOKEN for authenticated API requests.")

    try:
        # Fetch public events (page 1 contains the 30 most recent events)
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            stats["error"] = f"GitHub user '{username}' not found."
            logger.error(stats["error"])
            return stats
        elif response.status_code == 403 and "rate limit" in response.text.lower():
            stats["error"] = "GitHub API rate limit exceeded. Set a GITHUB_TOKEN to increase limits."
            logger.error(stats["error"])
            return stats
        
        response.raise_for_status()
        events = response.json()
        
        if not isinstance(events, list):
            stats["error"] = "Received unexpected response format from GitHub API."
            logger.error(stats["error"])
            return stats

        active_repos = set()
        
        for event in events:
            # Parse event creation time in UTC
            created_at_str = event.get("created_at")
            if not created_at_str:
                continue
                
            try:
                # GitHub timestamps are ISO strings in UTC (e.g. 2026-05-26T18:02:26Z)
                created_utc = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                # Convert event time to the target timezone
                created_local = created_utc.astimezone(target_tz)
            except ValueError as e:
                logger.warning(f"Error parsing timestamp {created_at_str}: {e}")
                continue
                
            # If the event occurred on the target date (today)
            if created_local.date() == target_date:
                stats["total_events"] += 1
                repo_name = event.get("repo", {}).get("name")
                
                # Check for commit activity
                if event.get("type") == "PushEvent":
                    if repo_name:
                        active_repos.add(repo_name)
                    
                    # Commits are stored in the payload
                    payload = event.get("payload", {})
                    # 'distinct_size' contains the number of unique commits in this push
                    commits_count = payload.get("distinct_size", len(payload.get("commits", [])))
                    stats["commits_today"] += commits_count
                
                # Track other types of activity (PRs, issues, repository creation)
                elif event.get("type") in ["PullRequestEvent", "IssuesEvent", "CreateEvent", "IssueCommentEvent"]:
                    if repo_name:
                        active_repos.add(repo_name)

        stats["repos_active"] = sorted(list(active_repos))
        stats["success"] = True
        logger.info(f"GitHub fetch successful. Commits today: {stats['commits_today']}. Active repos: {stats['repos_active']}")
        
    except requests.exceptions.RequestException as e:
        stats["error"] = f"Network error connecting to GitHub: {e}"
        logger.error(stats["error"])
    except Exception as e:
        stats["error"] = f"An unexpected error occurred parsing GitHub data: {e}"
        logger.error(stats["error"])
        
    return stats

if __name__ == "__main__":
    # Test execution
    from dotenv import load_dotenv
    load_dotenv()
    test_user = os.getenv("GITHUB_USERNAME", "octocat")
    print(f"Testing GitHub tracker for user '{test_user}':")
    result = fetch_github_activity(test_user)
    import pprint
    pprint.pprint(result)
