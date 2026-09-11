# Campaign Daily Report Emailer

Automated daily campaign performance reports pulled from a VICIdial dialer instance, formatted into HTML, and emailed to per-campaign client recipients.

## What it does

- Fetches **agent performance** and **outbound calling stats** from VICIdial's admin reporting pages for each campaign.
- Parses the raw report data (call stats, pause breakdown, hangup/status stats)....
- Tracks **year-to-date NONPAUSE hours** against a quota target per campaign.
- Builds a formatted HTML email report per campaign.
- Sends the report to each campaign's mapped client email(s), with a shared CC list......
- Runs on a daily schedule, or can be triggered manually for testing.

## Requirements

- Python 3.8+
- Packages: `requests`, `urllib3`, `beautifulsoup4`, `schedule`

Install dependencies:----
```bash
pip install requests urllib3 beautifulsoup4 schedule
```

## Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/gaurav07ag/campaign-daily-report-emailer.git
   cd campaign-daily-report-emailer
   ```

2. Create a `.env` file in the project root (this file is git-ignored and never committed):
   ```env
   VICI_USER=your_vicidial_username
   VICI_PASS=your_vicidial_password
   VICIDIAL_HOST=dialer.richierichleads.com

   GMAIL_USER=your_gmail_address@gmail.com
   GMAIL_APP_PASS=your_gmail_app_password
   ```

   > **Gmail App Password:** you need a Gmail *App Password*, not your regular Gmail password. Generate one from your Google Account → Security → 2-Step Verification → App Passwords.

3. Review the config section at the top of `campaign_daily_report.py`:
   - `CAMPAIGN_EMAILS` — maps each VICIdial campaign ID to its client recipient email(s).
   - `CAMPAIGN_NAMES` — maps each campaign ID to a friendly, client-facing display name.
   - `CC_EMAILS` — addresses always CC'd on every report.
   - `NONPAUSE_QUOTA_HOURS` — the YTD active-work-hours target used for the quota bullet.
   - `SEND_TIME` — the daily send time (24hr format, e.g. `"08:00"`).
   - `TEST_MODE` — when `True`, **all** emails are redirected to `TEST_RECIPIENT` and CC is suppressed. Set to `False` only when ready to send to real clients.

## Usage

```bash
# Run the scheduler — sends reports daily at SEND_TIME
python3 campaign_daily_report.py auto

# Send all campaign reports right now
python3 campaign_daily_report.py now

# Test a single campaign using yesterday's data
python3 campaign_daily_report.py test RACILJRE

# Test a single campaign with a specific date range
python3 campaign_daily_report.py testdate RACILJRE 2026-07-13 2026-07-14
```

## Notes & known limitations

- Report data is scraped from VICIdial's admin reporting pages (not a documented REST API), so parsing depends on VICIdial's existing text-report layout. Layout changes on the VICIdial side may require updates to the parsing logic in `parse_agent_performance`.
- SSL certificate verification is currently disabled (`verify=False`) for requests to the VICIdial host. Confirm this is acceptable for your environment before deploying.
- Failures are logged to the console only — there is no external alerting if a report fails to send.
- Keep `TEST_MODE = True` while making changes, and only switch it off once all recipients in `CAMPAIGN_EMAILS` and `CAMPAIGN_NAMES` have been confirmed.

## Security

- Never commit your `.env` file — it contains live credentials. It is already listed in `.gitignore`.
- This repository is intended to be **private**, since campaign IDs and client email addresses are stored directly in the source code.
