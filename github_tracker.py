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

def fetch_github_commits_history(username: str, start_date, end_date, target_tz) -> dict:
    """
    Queries the GitHub Search Commits API for commits by the given user.
    Returns a dictionary mapping local date string (YYYY-MM-DD) to a set of (commit_sha, repo_name) tuples.
    """
    commits_by_date = {}
    if not username:
        return commits_by_date

    # Query commits since start_date - 1 day to be timezone safe
    from datetime import timedelta
    since_date_utc = start_date - timedelta(days=1)
    import time
    nocache = int(time.time() * 1000)
    url = f"https://api.github.com/search/commits?q=author:{username}+committer-date:>={since_date_utc}&_nocache={nocache}"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CodingConsistencyTracker/1.0"
    }
    
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        logger.info("Using GITHUB_TOKEN for search commits API request.")
        
    try:
        logger.info(f"Querying GitHub Search Commits API for '{username}' since {since_date_utc}...")
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            for item in items:
                commit_sha = item.get("sha")
                commit_info = item.get("commit", {})
                author_info = commit_info.get("author", {})
                date_str = author_info.get("date")  # e.g., "2026-05-27T01:00:25.000+05:30"
                repo_name = item.get("repository", {}).get("full_name")
                
                if not date_str or not commit_sha:
                    continue
                    
                if date_str.endswith("Z"):
                    date_str = date_str.replace("Z", "+00:00")
                
                try:
                    dt_utc = datetime.fromisoformat(date_str)
                    dt_local = dt_utc.astimezone(target_tz)
                    local_date = dt_local.date()
                    
                    if start_date <= local_date <= end_date:
                        local_date_str = str(local_date)
                        if local_date_str not in commits_by_date:
                            commits_by_date[local_date_str] = set()
                        commits_by_date[local_date_str].add((commit_sha, repo_name))
                except ValueError as e:
                    logger.warning(f"Error parsing commit date {date_str}: {e}")
        else:
            logger.error(f"Search Commits API failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error fetching commits history: {e}")
        
    return commits_by_date

def fetch_github_activity(username: str) -> dict:
    """
    Fetches the GitHub activity for a given username for 'today'.
    Returns a dictionary of stats.
    """
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
    
    today_shas = set()
    active_repos = set()
    
    # 1. Fetch Search Commits API results for today
    history_commits = fetch_github_commits_history(username, target_date, target_date, target_tz)
    today_str = str(target_date)
    if today_str in history_commits:
        for sha, repo in history_commits[today_str]:
            today_shas.add(sha)
            if repo:
                active_repos.add(repo)
                
    # 2. Fetch Events API for real-time changes
    import time
    nocache = int(time.time() * 1000)
    url = f"https://api.github.com/users/{username}/events?_nocache={nocache}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CodingConsistencyTracker/1.0"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
        logger.info("Using GITHUB_TOKEN for Events API request.")

    try:
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
        
        for event in events:
            created_at_str = event.get("created_at")
            if not created_at_str:
                continue
                
            try:
                created_utc = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                created_local = created_utc.astimezone(target_tz)
            except ValueError as e:
                logger.warning(f"Error parsing timestamp {created_at_str}: {e}")
                continue
                
            if created_local.date() == target_date:
                stats["total_events"] += 1
                repo_name = event.get("repo", {}).get("name")
                
                if event.get("type") == "PushEvent":
                    if repo_name:
                        active_repos.add(repo_name)
                    
                    payload = event.get("payload", {})
                    # Try to extract SHAs from payload commits list
                    commits_list = payload.get("commits", [])
                    for c in commits_list:
                        c_sha = c.get("sha")
                        if c_sha:
                            today_shas.add(c_sha)
                            
                    # Fallback compare API check
                    before = payload.get("before")
                    head = payload.get("head")
                    if before and head and before != "0000000000000000000000000000000000000000":
                        compare_url = f"https://api.github.com/repos/{repo_name}/compare/{before}...{head}"
                        try:
                            comp_resp = requests.get(compare_url, headers=headers, timeout=5)
                            if comp_resp.status_code == 200:
                                compare_commits = comp_resp.json().get("commits", [])
                                for c in compare_commits:
                                    c_sha = c.get("sha")
                                    if c_sha:
                                        today_shas.add(c_sha)
                        except Exception as e:
                            logger.warning(f"Failed to compare commits for repo {repo_name}: {e}")
                    
                    # If we found no SHAs in this PushEvent payload, default to count distinct_size/size or 1
                    if not commits_list and (not before or before == "0000000000000000000000000000000000000000" or not head):
                        size = payload.get("distinct_size") or payload.get("size") or 1
                        for i in range(size):
                            today_shas.add(f"dummy_sha_{event.get('id')}_{i}")
                
                elif event.get("type") in ["PullRequestEvent", "IssuesEvent", "CreateEvent", "IssueCommentEvent"]:
                    if repo_name:
                        active_repos.add(repo_name)

        stats["commits_today"] = len(today_shas)
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

