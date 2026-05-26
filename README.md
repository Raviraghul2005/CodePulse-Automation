# 🚀 Coding Consistency Tracker & Email Automation System

A lightweight, production-ready Python automation tool that tracks your daily coding achievements across **GitHub** and **LeetCode**, maintains a history of your combined consistency streak, and emails you a beautiful HTML summary card every evening.

This system is completely free to run, modularly structured, and can be hosted locally or run serverlessly in the cloud using **GitHub Actions**.

---

## 📁 Project Structure

```text
CodePulse/
│
├── .github/
│   └── workflows/
│       └── schedule.yml    # GitHub Actions cron scheduler
├── logs/
│   ├── activity.log        # Rolling execution logs (local debugging)
│   └── history.json        # Persistent database tracking combined streaks
├── .env.example            # Template for environment configuration
├── .gitignore              # Files to exclude from Git tracking
├── requirements.txt        # Python package dependencies
├── github_tracker.py       # Module: Connects to GitHub API & parses commits
├── leetcode_tracker.py     # Module: Connects to LeetCode GraphQL & parses stats
├── email_sender.py         # Module: Assembles HTML/Text emails & handles SMTP
├── scheduler.py            # Local Daemon: Runs script persistently at a set time
└── main.py                 # Core Orchestrator: Integrates trackers, database, and email
```

---

## ⚙️ How It Works (The Code Explained)

### 1. `github_tracker.py`
This module fetches public activity from `https://api.github.com/users/{username}/events`.
* **GitHub API**: The events endpoint lists up to 30 recent actions (pushes, pull requests, issues).
* **Timezone Awareness**: The module converts UTC timestamps from GitHub to your configured timezone to accurately isolate actions performed on "today's" calendar date.
* **Commits Calculation**: It parses `PushEvent` objects and sums up the unique (`distinct_size`) commits made to each repository today.

### 2. `leetcode_tracker.py`
This module retrieves your stats using LeetCode's public GraphQL endpoint.
* **GraphQL Query**: It sends a single structured POST request to retrieve the difficulty breakdown (Easy, Medium, Hard solved questions) and your submission calendar.
* **Calendar Processing**: The calendar response maps Unix timestamps to submission counts. The tracker identifies timestamps falling on today's date to calculate your total submissions for the day.

### 3. `email_sender.py`
Handles communication, styling, and server logistics.
* **Sleek HTML Style**: Composes a responsive dark-themed email using modern card components, pill badges for active repos, and a multi-colored percentage bar showing your LeetCode difficulty ratio.
* **ASCII Text Fallback**: Includes a plain text fallback with ASCII progress bars (e.g. `[#####.....]`) for email clients that do not support HTML.
* **Motivational Quote API**: Queries the ZenQuotes API to load a fresh inspirational quote each day, failing back gracefully to a curated local list if the API is offline.
* **SMTP connection**: Sends emails securely over TLS (`smtp.gmail.com:587`) using Python's `smtplib`.

### 4. `main.py`
The orchestrator. It manages:
* **State & Persistence**: Creates the local `logs/` directory and writes rolling logs.
* **Combined Streak Logic**: Evaluates daily activity. If you committed to GitHub **OR** solved a LeetCode problem, it increments your combined streak. If you skip a day, the streak resets. This combined streak logic is tracked inside `logs/history.json`.

### 5. `scheduler.py`
A local execution daemon. If you decide to host this on a home server (like a Raspberry Pi or local PC), this script schedules `main.py` to run daily at a designated local time (e.g. `20:00` / 8:00 PM) using the Python `schedule` library.

---

## 📧 Gmail App Password Setup (Critical Step)

For security reasons, Gmail blocks external scripts from logging in with your main password. You must generate an **App Password**:

1. Go to your **Google Account Settings** (https://myaccount.google.com/).
2. Enable **2-Step Verification** in the **Security** tab (if not already enabled).
3. Search for **App passwords** in the search bar or go directly to the page.
4. Select **Create a new app password**, enter a name (e.g., `Coding Streak Tracker`), and click **Create**.
5. Copy the generated **16-character code** (formatted like `xxxx xxxx xxxx xxxx`).
6. Paste this code into your `.env` file as the `EMAIL_PASSWORD` variable.

---

## 💻 Local Setup and Run

### 1. Installation
Ensure you have Python 3.8+ installed. Open your terminal in the project directory:

```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate    # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Duplicate `.env.example`, rename it to `.env`, and fill in your details:

```ini
EMAIL_ADDRESS=your_gmail@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
RECEIVER_EMAIL=your_receiver_email@gmail.com
GITHUB_USERNAME=your_github_username
LEETCODE_USERNAME=your_leetcode_username

# Optional settings
SCHEDULE_TIME=20:00         # Time to run local scheduler (24hr format)
TIMEZONE_OFFSET=5.5         # UTC offset for your local timezone (e.g., 5.5 for IST)
```

### 3. Execution
You can test the execution immediately by running `main.py`:

```bash
python main.py
```
Check your inbox! You should receive your summary email. If you have no activity today, you'll see a warning alert.

To run the local scheduling daemon (keeps running in the background):

```bash
python scheduler.py
```

---

## ☁️ Free Cloud Deployment: GitHub Actions (Recommended)

You can run this tracker for free in the cloud without keeping your PC powered on.

### How it remains persistent:
GitHub Actions uses virtual servers that spin up, run the script, and shut down. Since file updates are normally lost, the workflow is configured to **commit and push** `logs/history.json` and `logs/activity.log` back to your GitHub repository automatically. This keeps your streak history intact forever!

### Step-by-Step Setup:

1. **Create a Private GitHub Repository**
   Create a new private repository on GitHub (private is recommended since your history contains logs, usernames, and you don't want configuration leaks). Push your project code:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <your-repo-link>
   git push -u origin main
   ```

2. **Allow GitHub Actions to Write to Your Repository**
   * On your GitHub repository page, go to **Settings** > **Actions** > **General**.
   * Scroll down to **Workflow permissions**.
   * Select **Read and write permissions**.
   * Click **Save**.

3. **Configure Repository Secrets**
   Go to **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.
   
   You can copy-paste your entire local `.env` configuration at once:
   
   * **Name**: `ENV_FILE`
   * **Secret**: (Copy and paste the entire content of your local `.env` file)

   *(Optional) If you want to use the GitHub API without getting rate-limited during high-traffic times, you can also add a secret named `GITHUB_TOKEN` containing your GitHub Personal Access Token (PAT).*

4. **Adjust Scheduled Time (Cron)**
   By default, the workflow in `.github/workflows/schedule.yml` is scheduled to run at `14:30 UTC` (which corresponds to 8:00 PM IST / UTC+5:30). If you live in a different timezone, update the cron line:
   ```yaml
   on:
     schedule:
       - cron: '30 14 * * *' # Format: Minute Hour Day Month Day-of-week
   ```
   *Note: GitHub Actions cron scheduling is always in UTC.*

5. **Test Your Action**
   * Go to the **Actions** tab on your GitHub repository.
   * Click on **Coding Consistency Tracker** in the left menu.
   * Click the **Run workflow** dropdown, choose your branch, and click **Run workflow**.
   * Watch the process run! Once completed, check your inbox and verify that `logs/history.json` has been updated in your repository files.

---

## 📈 Share Your Progress!
Want to showcase this on LinkedIn or X?
* **Post template**:
  > "Built a serverless Python automation system to hold myself accountable! 🚀 It tracks my GitHub commits and LeetCode solved count daily, saves my streaks in JSON, and emails me a beautiful progress card every evening at 8 PM. Powered by GitHub Actions & Python. Time to compound consistency! 💻✨"
