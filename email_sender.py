import os
import smtplib
import logging
import random
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# List of backup motivational quotes if the online API is unavailable or rate-limited
DEFAULT_QUOTES = [
    {"quote": "Consistency compounds. Keep showing up.", "author": "Unknown"},
    {"quote": "The secret of your future is hidden in your daily routine.", "author": "Mike Murdock"},
    {"quote": "It's not what we do once in a while that shapes our lives. It's what we do consistently.", "author": "Tony Robbins"},
    {"quote": "Success is the sum of small efforts, repeated day in and day out.", "author": "Robert Collier"},
    {"quote": "Small daily improvements over time lead to stunning results.", "author": "Robin Sharma"},
    {"quote": "First forget inspiration. Habit is more dependable. Habit will sustain you whether you're inspired or not.", "author": "Octavia Butler"},
    {"quote": "We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "author": "Aristotle"},
    {"quote": "Continuous improvement is better than delayed perfection.", "author": "Mark Twain"},
    {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"quote": "Action is the foundational key to all success.", "author": "Pablo Picasso"}
]

def fetch_motivational_quote() -> dict:
    """
    Fetches a random motivational quote from ZenQuotes API.
    If the API fails, returns a random quote from the local backup list.
    """
    url = "https://zenquotes.io/api/random"
    try:
        logger.info("Fetching motivational quote from ZenQuotes API...")
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                quote = data[0].get("q")
                author = data[0].get("a")
                logger.info("Quote fetched successfully.")
                return {"quote": quote, "author": author}
    except Exception as e:
        logger.warning(f"Could not fetch quote from API ({e}). Using local fallback.")
    
    return random.choice(DEFAULT_QUOTES)

def build_ascii_progress_bar(val: int, total: int, length: int = 15) -> str:
    """
    Builds a simple ASCII progress bar string.
    Example: [#####..........]
    """
    if total <= 0:
        return "[" + "." * length + "]"
    filled_length = int(round((val / total) * length))
    bar = "#" * filled_length + "." * (length - filled_length)
    return f"[{bar}]"

def assemble_plain_text_email(recipient_name: str, github_stats: dict, leetcode_stats: dict, quote_dict: dict) -> str:
    """
    Generates a clean plain text version of the email, featuring ASCII progress bars.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    
    # Calculate LeetCode progress details
    lt_solved = leetcode_stats.get("total_solved", 0)
    easy = leetcode_stats.get("easy_solved", 0)
    medium = leetcode_stats.get("medium_solved", 0)
    hard = leetcode_stats.get("hard_solved", 0)
    
    # ASCII Progress Bars
    easy_bar = build_ascii_progress_bar(easy, lt_solved)
    med_bar = build_ascii_progress_bar(medium, lt_solved)
    hard_bar = build_ascii_progress_bar(hard, lt_solved)
    
    # Check if active today
    active_today = (github_stats.get("commits_today", 0) > 0) or (leetcode_stats.get("submissions_today", 0) > 0)
    activity_nudge = ""
    if not active_today:
        activity_nudge = (
            "⚠️ ATTENTION: No coding activity was detected today!\n"
            "Remember, consistency is key. Even solving one easy problem or writing\n"
            "one line of code keeps your momentum going. Don't break the streak!\n\n"
        )
    
    body = f"""Daily Coding Summary - {date_str} 🚀

Hey {recipient_name},

Here is your coding progress summary for today:

{activity_nudge}========================================
LEETCODE STATS
========================================
* Total Solved: {lt_solved}
  - Easy:   {easy_bar} {easy}
  - Medium: {med_bar} {medium}
  - Hard:   {hard_bar} {hard}
* Today's Activity: {leetcode_stats.get("submissions_today", 0)} submissions
* LeetCode Streak: {leetcode_stats.get("current_streak", 0)} days
* Combined Coding Streak: {leetcode_stats.get("combined_streak", 0)} days (Max: {leetcode_stats.get("combined_max_streak", 0)})

========================================
GITHUB STATS
========================================
* Commits Today: {github_stats.get("commits_today", 0)}
* Total Events: {github_stats.get("total_events", 0)}
* Active Repositories: {", ".join(github_stats.get("repos_active", [])) if github_stats.get("repos_active") else "None"}

========================================
DAILY MOTIVATION
========================================
"{quote_dict['quote']}"
-- {quote_dict['author']}

Consistency compounds. Keep building.
"""
    return body

def assemble_html_email(recipient_name: str, github_stats: dict, leetcode_stats: dict, quote_dict: dict) -> str:
    """
    Generates a polished HTML email with a Swiss Editorial newsletter design.
    Uses table-based layout with fully inlined styles and responsive media queries.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    day_of_week = datetime.now().strftime("%A")
    
    # Extract stats
    gh_commits = github_stats.get("commits_today", 0)
    gh_events = github_stats.get("total_events", 0)
    gh_repos = github_stats.get("repos_active", [])
    
    lc_solved = leetcode_stats.get("total_solved", 0)
    lc_easy = leetcode_stats.get("easy_solved", 0)
    lc_medium = leetcode_stats.get("medium_solved", 0)
    lc_hard = leetcode_stats.get("hard_solved", 0)
    lc_subs = leetcode_stats.get("submissions_today", 0)
    lc_streak = leetcode_stats.get("current_streak", 0)
    combined_streak = leetcode_stats.get("combined_streak", 0)
    combined_max_streak = leetcode_stats.get("combined_max_streak", 0)
    
    # Calculate percentages for the breakdown
    if lc_solved > 0:
        easy_pct = round((lc_easy / lc_solved) * 100, 1)
        medium_pct = round((lc_medium / lc_solved) * 100, 1)
        hard_pct = round((lc_hard / lc_solved) * 100, 1)
    else:
        easy_pct = medium_pct = hard_pct = 0
        
    active_today = (gh_commits > 0) or (lc_subs > 0)
    
    # Status configuration
    if active_today:
        status_text = "ACTIVE TODAY"
        status_color = "#15803D"  # Editorial deep green
    else:
        status_text = "INACTIVE TODAY (ACTION REQUIRED)"
        status_color = "#B91C1C"  # Editorial crimson
    
    # Repos formatting
    if gh_repos:
        repo_rows = ""
        for repo in gh_repos:
            display_name = repo.split("/")[-1] if "/" in repo else repo
            repo_rows += f'<tr><td style="padding: 3px 0; color: #1C1917; font-family: Consolas, \'Courier New\', Courier, monospace; font-size: 13px;">↳ {display_name}</td></tr>'
    else:
        repo_rows = '<tr><td style="padding: 3px 0; color: #78716C; font-family: Consolas, \'Courier New\', Courier, monospace; font-size: 13px; font-style: italic;">No pushes recorded today</td></tr>'

    # Load history data and compile the last 7 calendar days of activity
    import json
    from datetime import timedelta
    from github_tracker import get_target_date_and_tz
    
    # Get target date using configured timezone
    target_date, _ = get_target_date_and_tz()
    
    # Generate the last 7 calendar dates ending today (from today-6 to today)
    last_7_dates = [target_date - timedelta(days=i) for i in range(6, -1, -1)]
    
    # Load logs from history.json
    history_path = os.path.join("logs", "history.json")
    daily_logs = {}
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                history_data = json.load(f)
                daily_logs = history_data.get("daily_logs", {})
        except Exception as e:
            logger.warning(f"Could not load history for email: {e}")

    # Build history contribution grid HTML for the last 7 calendar days
    block_cells = ""
    for d in last_7_dates:
        date_str_key = str(d)
        
        # Check if active that day in logs
        active = False
        if date_str_key in daily_logs:
            active = daily_logs[date_str_key].get("active", False)
            
        day_letter = d.strftime("%a")[0]  # M, T, W...
        date_num = d.strftime("%d")       # 01-31
        
        # Color coding:
        # Active: soft mint green with solid emerald green border
        # Inactive: desaturated soft stone grey
        if active:
            bg_color = "#D1FAE5"      # Light mint green
            border_color = "#10B981"  # Emerald green border
            text_color = "#047857"    # Dark emerald text
        else:
            bg_color = "#F5F5F4"      # Inactive day
            border_color = "#D6D3D1"  # Soft border
            text_color = "#78716C"    # Soft grey text

        block_cells += f"""
        <td style="padding-right: 6px;" align="center">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="background-color: {bg_color}; border: 1px solid {border_color}; width: 32px; height: 32px; text-align: center;">
                <tr>
                    <td valign="middle" style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; font-weight: bold; color: {text_color}; line-height: 1;">
                        {date_num}
                    </td>
                </tr>
            </table>
            <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 9px; color: #78716C; display: block; margin-top: 4px; text-transform: uppercase;">
                {day_letter}
            </span>
        </td>
        """

    # Build LeetCode Difficulty Visual Bars
    lc_bars_html = f"""
    <div style="margin-bottom: 14px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; color: #78716C; text-transform: uppercase; margin-bottom: 4px;">
            <tr>
                <td>Easy</td>
                <td align="right" style="color: #1C1917; font-weight: bold;">{lc_easy} <span style="font-weight: normal; color: #78716C;">/ {lc_solved} ({easy_pct}%)</span></td>
            </tr>
        </table>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #FAF8F5; border: 1px solid #E7E5E4;">
            <tr>
                <td style="height: 6px; padding: 0;">
                    <table role="presentation" width="{easy_pct}%" cellpadding="0" cellspacing="0" border="0" style="height: 6px;">
                        <tr>
                            <td style="background-color: #86EFAC; height: 6px; line-height: 0; font-size: 0; padding: 0;"></td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
    
    <div style="margin-bottom: 14px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; color: #78716C; text-transform: uppercase; margin-bottom: 4px;">
            <tr>
                <td>Medium</td>
                <td align="right" style="color: #1C1917; font-weight: bold;">{lc_medium} <span style="font-weight: normal; color: #78716C;">/ {lc_solved} ({medium_pct}%)</span></td>
            </tr>
        </table>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #FAF8F5; border: 1px solid #E7E5E4;">
            <tr>
                <td style="height: 6px; padding: 0;">
                    <table role="presentation" width="{medium_pct}%" cellpadding="0" cellspacing="0" border="0" style="height: 6px;">
                        <tr>
                            <td style="background-color: #FEF08A; height: 6px; line-height: 0; font-size: 0; padding: 0;"></td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
    
    <div>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; color: #78716C; text-transform: uppercase; margin-bottom: 4px;">
            <tr>
                <td>Hard</td>
                <td align="right" style="color: #1C1917; font-weight: bold;">{lc_hard} <span style="font-weight: normal; color: #78716C;">/ {lc_solved} ({hard_pct}%)</span></td>
            </tr>
        </table>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #FAF8F5; border: 1px solid #E7E5E4;">
            <tr>
                <td style="height: 6px; padding: 0;">
                    <table role="presentation" width="{hard_pct}%" cellpadding="0" cellspacing="0" border="0" style="height: 6px;">
                        <tr>
                            <td style="background-color: #FCA5A5; height: 6px; line-height: 0; font-size: 0; padding: 0;"></td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </div>
    """

    # Inactive nudge block
    nudge_block = ""
    if not active_today:
        nudge_block = f"""
        <!-- Warning alert -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 32px; border-left: 3px solid #B91C1C; background-color: #FEF2F2;">
            <tr>
                <td style="padding: 16px; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; line-height: 1.6; color: #991B1B;">
                    <strong>Attention Required:</strong> No coding activity has been recorded on GitHub or LeetCode today. Solve a problem or commit code to maintain your combined streak of <strong>{combined_streak} days</strong>.
                </td>
            </tr>
        </table>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePulse Report</title>
    <style>
        @media only screen and (max-width: 480px) {{
            .mobile-container {{
                padding: 24px 20px 0 20px !important;
            }}
            .mobile-col {{
                display: block !important;
                width: 100% !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                border-left: none !important;
                border-top: 1px solid #E7E5E4 !important;
                margin-top: 24px !important;
                padding-top: 24px !important;
            }}
            .mobile-col-first {{
                display: block !important;
                width: 100% !important;
                padding-left: 0 !important;
                padding-right: 0 !important;
                margin-bottom: 24px !important;
            }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #FAF8F5; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;">

    <!-- Background wrapper -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #FAF8F5;">
        <tr>
            <td align="center" style="padding: 40px 16px;">

                <!-- Container -->
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 560px; background-color: #FFFFFF; border: 1px solid #E7E5E4; text-align: left;">
                    
                    <!-- Header Padding Block -->
                    <tr>
                        <td class="mobile-container" style="padding: 40px 40px 0 40px;">
                            
                            <!-- Category and title -->
                            <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; font-weight: bold; letter-spacing: 0.15em; color: #78716C; text-transform: uppercase; display: block; margin-bottom: 8px;">
                                CodePulse // Progress Ledger
                            </span>
                            <h1 style="font-family: Georgia, 'Times New Roman', serif; font-size: 32px; font-weight: normal; color: #1C1917; margin: 0 0 4px 0; line-height: 1.1;">
                                {day_of_week}
                            </h1>
                            <p style="font-family: Georgia, 'Times New Roman', serif; font-size: 15px; font-style: italic; color: #78716C; margin: 0 0 24px 0;">
                                {date_str}
                            </p>

                            <!-- Status Line -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top: 1px solid #E7E5E4; border-bottom: 1px solid #E7E5E4; margin-bottom: 32px;">
                                <tr>
                                    <td style="padding: 12px 0; font-family: Consolas, 'Courier New', Courier, monospace; font-size: 12px; color: #1C1917;">
                                        STATUS: <strong style="color: {status_color};">{status_text}</strong>
                                    </td>
                                    <td align="right" style="padding: 12px 0; font-family: Consolas, 'Courier New', Courier, monospace; font-size: 12px; color: #78716C;">
                                        COMBINED STREAK: {combined_streak} DAYS
                                    </td>
                                </tr>
                            </table>

                            <!-- Greeting -->
                            <p style="font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6; color: #292524; margin: 0 0 32px 0;">
                                Hello {recipient_name},<br><br>
                                Here is the detailed catalog of your programming activity. Consistency shapes competence.
                            </p>

                            {nudge_block}

                            <!-- Section I: LeetCode -->
                            <h2 style="font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: normal; border-bottom: 1px solid #E7E5E4; padding-bottom: 6px; margin: 0 0 20px 0; color: #1C1917;">
                                I. LeetCode Metrics
                            </h2>

                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    <!-- Solved Stats -->
                                    <td class="mobile-col-first" width="50%" valign="top" style="padding-right: 20px;">
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-bottom: 4px;">Total Solved</span>
                                        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 44px; line-height: 1; color: #1C1917; font-weight: normal; display: block;">{lc_solved}</span>
                                        
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-top: 20px; margin-bottom: 4px;">Today's Submissions</span>
                                        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; line-height: 1; color: #1C1917; font-weight: normal; display: block;">{lc_subs}</span>
                                    </td>
                                    
                                    <!-- Visual Difficulty Breakdown -->
                                    <td class="mobile-col" width="50%" valign="top" style="border-left: 1px solid #E7E5E4; padding-left: 20px;">
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-bottom: 12px;">Difficulty Details</span>
                                        {lc_bars_html}
                                    </td>
                                </tr>
                            </table>

                            <!-- Section II: GitHub -->
                            <h2 style="font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: normal; border-bottom: 1px solid #E7E5E4; padding-bottom: 6px; margin: 0 0 20px 0; color: #1C1917;">
                                II. GitHub Metrics
                            </h2>

                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    <!-- Commits/Events -->
                                    <td class="mobile-col-first" width="50%" valign="top" style="padding-right: 20px;">
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-bottom: 4px;">Commits Today</span>
                                        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 44px; line-height: 1; color: #1C1917; font-weight: normal; display: block;">{gh_commits}</span>
                                        
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-top: 20px; margin-bottom: 4px;">Total Events</span>
                                        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; line-height: 1; color: #1C1917; font-weight: normal; display: block;">{gh_events}</span>
                                    </td>
                                    
                                    <!-- Active Repos -->
                                    <td class="mobile-col" width="50%" valign="top" style="border-left: 1px solid #E7E5E4; padding-left: 20px;">
                                        <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-bottom: 12px;">Active Repositories</span>
                                        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                                            {repo_rows}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Section III: Consistency & Weekly History -->
                            <h2 style="font-family: Georgia, 'Times New Roman', serif; font-size: 18px; font-weight: normal; border-bottom: 1px solid #E7E5E4; padding-bottom: 6px; margin: 0 0 20px 0; color: #1C1917;">
                                III. Consistency & Weekly Outlook
                            </h2>

                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px; font-family: Consolas, 'Courier New', Courier, monospace; font-size: 13px; color: #292524;">
                                <tr>
                                    <td style="padding: 8px 0; color: #78716C;">Combined Streak</td>
                                    <td align="right" style="padding: 8px 0; color: #1C1917; font-weight: bold;">{combined_streak} days <span style="font-size: 11px; font-weight: normal; color: #78716C;">(Max: {combined_max_streak})</span></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; border-top: 1px solid #F5F5F4; color: #78716C;">LeetCode Streak</td>
                                    <td align="right" style="padding: 8px 0; border-top: 1px solid #F5F5F4; color: #1C1917; font-weight: bold;">{lc_streak} days</td>
                                </tr>
                            </table>
                            
                            <!-- Weekly contribution grid -->
                            <span style="font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; color: #78716C; display: block; margin-bottom: 10px;">Weekly History</span>
                            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 32px;">
                                <tr>
                                    {block_cells}
                                </tr>
                            </table>

                            <!-- Section IV: Motivation -->
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top: 8px; margin-bottom: 40px; border-top: 1px solid #E7E5E4; border-bottom: 1px solid #E7E5E4;">
                                <tr>
                                    <td align="center" style="padding: 36px 20px;">
                                        <p style="margin: 0 0 12px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.6; font-style: italic; color: #1C1917;">
                                            &#8220;{quote_dict['quote']}&#8221;
                                        </p>
                                        <p style="margin: 0; font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #78716C;">
                                            &#8212; {quote_dict['author']}
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Footer -->
                            <p style="margin: 0 0 40px 0; font-family: Consolas, 'Courier New', Courier, monospace; font-size: 11px; text-align: center; color: #A8A29E; line-height: 1.8; letter-spacing: 0.05em; text-transform: uppercase;">
                                Consistency compounds. Keep building.
                                <br>
                                <span style="font-size: 10px; color: #D6D3D1;">Sent by CodePulse</span>
                            </p>

                        </td>
                    </tr>
                </table>

            </td>
        </tr>
    </table>

</body>
</html>"""
    return html

def send_daily_email(github_stats: dict, leetcode_stats: dict) -> bool:
    """
    Assembles and sends the daily summary email.
    Reads credentials and details from environment variables.
    """
    # Load settings from environment
    sender_email = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")
    
    # Configure names
    github_user = github_stats.get("username", "Ravi")
    recipient_name = github_user.capitalize()
    
    if not sender_email or not email_password or not receiver_email:
        logger.error("Email configurations (EMAIL_ADDRESS, EMAIL_PASSWORD, RECEIVER_EMAIL) are not fully set in the environment.")
        return False
        
    # Get a motivational quote
    quote_dict = fetch_motivational_quote()
    
    # Check if active today to set the subject accordingly
    active_today = (github_stats.get("commits_today", 0) > 0) or (leetcode_stats.get("submissions_today", 0) > 0)
    subject = "Daily Coding Summary 🚀" if active_today else "Coding Consistency Alert! ⚠️ Keep the streak alive!"
    
    # Create the email message container
    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    
    # Generate content versions
    text_content = assemble_plain_text_email(recipient_name, github_stats, leetcode_stats, quote_dict)
    html_content = assemble_html_email(recipient_name, github_stats, leetcode_stats, quote_dict)
    
    # Attach both parts (client will render HTML if possible, otherwise fall back to text)
    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))
    
    # Send email via Gmail SMTP
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    try:
        logger.info(f"Connecting to SMTP server at {smtp_server}:{smtp_port}...")
        # Secure TLS connection setup
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade connection to secure encrypted TLS
        
        logger.info("Logging in to email account...")
        server.login(sender_email, email_password)
        
        logger.info(f"Sending email to {receiver_email}...")
        server.sendmail(sender_email, receiver_email, message.as_string())
        
        logger.info("Email sent successfully!")
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error("Authentication failed. Double check your EMAIL_ADDRESS and ensure you are using an App Password instead of your regular password.")
        logger.error(f"Details: {e}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        
    return False

if __name__ == "__main__":
    # Test compilation and print preview
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    from dotenv import load_dotenv
    load_dotenv()
    
    dummy_gh = {"success": True, "username": "ravicodes", "commits_today": 3, "total_events": 5, "repos_active": ["streak-tracker", "leetcode-solutions"]}
    dummy_lc = {"success": True, "username": "ravicodes", "total_solved": 154, "easy_solved": 80, "medium_solved": 60, "hard_solved": 14, "submissions_today": 2, "current_streak": 5, "combined_streak": 8, "combined_max_streak": 20}
    
    print("Generating and printing Plain Text email preview:")
    quote = {"quote": "Consistency compounds.", "author": "Unknown"}
    print(assemble_plain_text_email("Ravi", dummy_gh, dummy_lc, quote))
    print("\n--- Preview compilation completed. ---")
