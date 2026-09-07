#!/usr/bin/env python3
# ================================================
# RICHIE RICH LEADS — Daily Campaign Report Emailer
# ================================================

import requests
import urllib3
import json
import os
import schedule
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── CONFIG ──────────────────────────────────────
def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

VICI_USER      = os.environ.get("VICI_USER", "")
VICI_PASS      = os.environ.get("VICI_PASS", "")
VICIDIAL_HOST  = os.environ.get("VICIDIAL_HOST", "dialer.richierichleads.com")
VICIDIAL_BASE  = f"https://{VICI_USER}:{VICI_PASS}@{VICIDIAL_HOST}/vicidial"

GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS = os.environ.get("GMAIL_APP_PASS", "")

# ── TEST MODE ────────────────────────────────────
# While True: every campaign's report is redirected to TEST_RECIPIENT
# instead of the real client email(s), and CC is suppressed.
# Flip to False when you're ready to send to actual clients again.
TEST_MODE      = False
TEST_RECIPIENT = ["bipinvs014@gmail.com"]

# ── CAMPAIGN → CLIENT EMAIL MAPPING ─────────────
CAMPAIGN_EMAILS = {
    "RACILJRE" : ["bipinvs014@gmail.com"],
    "RACAZSPX" : ["justinn@sparxexteriors.com"],
    "RACGAEVO" : ["bipinvs014@gmail.com"],
    "RACTXINV" : ["bipinvs014@gmail.com"],
    "RACMOBOL" : ["robroy.bold@gmail.com"],
    "RACMDTAP" : ["bipinvs014@gmail.com"],
    "RACTXVCG" : ["bipinvs014@gmail.com"],
    "LAPRCR"   : ["bipinvs014@gmail.com"],
    "RACINALE" : ["bipinvs014@gmail.com"],
    "RACAZEVG" : ["codylee12333@gmail.com"],
    "RACINPLS" : ["dishman@platinumlosssolutions.com"],
    "RACTXRRC" : ["info@republicbuilt.com"],
    

}

# ── CAMPAIGN → CLIENT-FACING DISPLAY NAME ───────
# Clients don't know what "RACILJRE" means — this is the friendly name used
# in the email subject line and report header instead of the raw campaign ID.
# Pull the real value from the "Campaign Name" field on each campaign's
# VICIdial admin page (Campaigns → Basic View). Only RACILJRE is confirmed
# below — please fill in the rest before turning TEST_MODE off.
CAMPAIGN_NAMES = {
    "RACILJRE" : "Rent-A-Caller IL Insur Jjr Roofing and EXT",  # confirmed from VICIdial admin page
    "RACAZSPX" : "RACAZSPX",   # TODO: replace with the Campaign Name field from VICIdial
    "RACGAEVO" : "RACGAEVO",   # TODO
    "RACTXINV" : "RACTXINV",   # TODO
    "RACMOBOL" : "RACMOBOL",   # TODO
    "RACMDTAP" : "RACMDTAP",   # TODO
    "RACTXVCG" : "RACTXVCG",   # TODO
    "LAPRCR"   : "LAPRCR",     # TODO
    "RACINALE" : "RACINALE",
    "RACAZEVG" : "RACAZEVG",
    "RACINPLS" : "RACINPLS",
    "RACTXRRC" : "RACTXRRC"# 
    
    
}

def get_campaign_name(campaign_id):
    """Friendly, client-facing campaign name. Falls back to the raw ID if not mapped."""
    return CAMPAIGN_NAMES.get(campaign_id, campaign_id)


# ── CC EMAILS (always copied on every report) ────
# Suppressed automatically while TEST_MODE is True.
CC_EMAILS = ["Richard@theroofingnetwork.com", "alpha@theroofingnetwork.com"]

def resolve_recipients(campaign_id):
    """Return (to_emails, cc_emails) for a campaign, honoring TEST_MODE."""
    if TEST_MODE:
        return TEST_RECIPIENT, []
    return CAMPAIGN_EMAILS.get(campaign_id, ["bipinvs014@gmail.com"]), CC_EMAILS

# ── SEND TIME ───────────────────────────────────
# Change this to whatever time you want the report sent daily (24hr format)
SEND_TIME = "08:00"  # 8:00 AM — update when client timezones confirmed

# ── DATE RANGE ──────────────────────────────────
# Report covers yesterday (previous full day)
def get_report_dates():
    today     = datetime.now()
    yesterday = today - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


# ── NONPAUSE QUOTA TRACKING ──────────────────────
# Tracks cumulative active work time (NONPAUSE) against a target, measured
# from Jan 1 of the current year through today — NOT the single report day.
# Adjust the number below to whatever the real target is per campaign.
NONPAUSE_QUOTA_HOURS = 160

def get_ytd_dates():
    """Jan 1 of the current year through today, as (start_date, end_date) strings."""
    today = datetime.now()
    start = today.replace(month=1, day=1).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    return start, end


def hms_to_hours(hms):
    """Convert an 'H:MM:SS' (or 'HHH:MM:SS') string into a float number of hours."""
    if not hms:
        return None
    try:
        parts = hms.strip().split(":")
        if len(parts) != 3:
            return None
        h, m, s = parts
        return int(h) + int(m) / 60 + int(s) / 3600
    except (ValueError, TypeError):
        return None

# ────────────────────────────────────────────────

def fetch_url(url, max_retries=5, timeout=180):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, verify=False, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                return resp.text
            else:
                print(f"   ❌ HTTP {resp.status_code}")
                return None
        except requests.exceptions.Timeout:
            # Covers BOTH ConnectTimeout (couldn't reach the server) and
            # ReadTimeout (connected fine, but the server took too long to
            # respond — common on multi-day date ranges with lots of calls).
            wait = 15 * attempt
            print(f"   ⏳ Timeout attempt {attempt}/{max_retries}, retrying in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    print(f"   ❌ Gave up after {max_retries} timeout retries")
    return None


def extract_pre_text(html):
    soup = BeautifulSoup(html, "html.parser")
    pre_tags = soup.find_all("pre")
    if not pre_tags:
        return None
    return max((p.get_text() for p in pre_tags), key=len)


def parse_agent_performance(html):
    """Parse agent performance detail — returns two sections:
    call_stats rows and pause_breakdown rows."""
    pre_text = extract_pre_text(html)
    if not pre_text:
        return [], []

    lines = pre_text.split("\n")

    # ── CALL STATS table ──
    call_stats = []
    cs_header  = None
    in_cs      = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and "USER NAME" in s.upper() and "CALLS" in s.upper() and "NONPAUSE" not in s.upper():
            cs_header = [c.strip() for c in s.strip("|").split("|")]
            in_cs = True
            continue
        if in_cs:
            if not s.startswith("|"):
                if s == "" or s.startswith("+"):
                    continue
                else:
                    break
            if "USER NAME" in s.upper() or "TOTALS" in s.upper():
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and cells[0]:
                call_stats.append(cells)

    # ── PAUSE BREAKDOWN table ──
    pause_rows = []
    pb_header  = None
    in_pb      = False
    pb_totals  = None
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and "USER NAME" in s.upper() and "NONPAUSE" in s.upper():
            pb_header = [c.strip() for c in s.strip("|").split("|")]
            in_pb = True
            continue
        if in_pb:
            if not s.startswith("|"):
                if s == "" or s.startswith("+"):
                    continue
                else:
                    break
            if "USER NAME" in s.upper():
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not cells or not cells[0]:
                continue
            if "TOTALS" in s.upper():
                pb_totals = cells
                continue
            pause_rows.append(cells)

    return (cs_header, call_stats), (pb_header, pause_rows, pb_totals)


def fetch_outbound_stats(campaign_id, start_date, end_date):
    """Fetch outbound calling report for a campaign."""
    url = (
        f"{VICIDIAL_BASE}/AST_VDADstats.php"
        f"?agent_hours=&DB=0&outbound_rate=&costformat=&print_calls="
        f"&query_date={start_date}&end_date={end_date}"
        f"&group%5B%5D={campaign_id}"
        f"&user_group%5B%5D=--ALL--"
        f"&report_display_type=TEXT&SUBMIT=SUBMIT"
    )
    html = fetch_url(url)
    if not html:
        return None
    pre_text = extract_pre_text(html)
    return pre_text


def fetch_agent_performance(campaign_id, start_date, end_date):
    """Fetch agent performance detail for a campaign."""
    url = (
        f"{VICIDIAL_BASE}/AST_agent_performance_detail.php"
        f"?DB=0"
        f"&query_date={start_date}&query_time=00%3A00%3A00"
        f"&end_date={end_date}&end_time=23%3A59%3A59"
        f"&group%5B%5D={campaign_id}"
        f"&user_group%5B%5D=--ALL--"
        f"&shift=ALL&report_display_type=TEXT&SUBMIT=SUBMIT"
    )
    return fetch_url(url)


def fetch_ytd_nonpause_hours(campaign_id):
    """Total NONPAUSE (active work) hours for this campaign from Jan 1 of the
    current year through today. Used to track progress against
    NONPAUSE_QUOTA_HOURS — a separate, wider-range fetch from the single-day
    report data."""
    start_date, end_date = get_ytd_dates()
    ap_html = fetch_agent_performance(campaign_id, start_date, end_date)
    if not ap_html:
        return None

    _, (pb_header, _, pb_totals) = parse_agent_performance(ap_html)
    if not pb_header or not pb_totals:
        return None

    # Same right-alignment fix as elsewhere: the TOTALS row collapses the
    # leading identifier columns, so its NONPAUSE value sits at
    # (header_index - offset), not header_index.
    offset = len(pb_header) - len(pb_totals)
    for i, h in enumerate(pb_header):
        if "NONPAUSE" in h.upper():
            candidate = i - offset
            if 0 <= candidate < len(pb_totals):
                return hms_to_hours(pb_totals[candidate])
            break
    return None


def rows_to_html_table(header, rows, highlight_col=None, totals_row=None):
    """Convert header + rows into a styled HTML table.
    highlight_col: column name to bold/highlight (e.g. 'NONPAUSE')"""
    if not header or not rows:
        return "<p style='color:#888;'>No data available.</p>"

    highlight_idx = None
    if highlight_col:
        for i, h in enumerate(header):
            if highlight_col.upper() in h.upper():
                highlight_idx = i
                break

    th_style = "background:#2d3748;color:#e2e8f0;padding:8px 10px;text-align:left;font-size:12px;white-space:nowrap;font-weight:500;"
    td_style = "padding:7px 10px;font-size:12px;border-bottom:1px solid #f0f0f0;white-space:nowrap;color:#4a5568;"
    hl_style = "padding:7px 10px;font-size:12px;border-bottom:1px solid #f0f0f0;white-space:nowrap;background:#fffbeb;font-weight:600;color:#92400e;"

    html = '<div style="overflow-x:auto;"><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;min-width:600px;">'
    html += "<thead><tr>"
    for h in header:
        html += f'<th style="{th_style}">{h}</th>'
    html += "</tr></thead><tbody>"

    for ri, row in enumerate(rows):
        bg = "#f9f9f9" if ri % 2 == 0 else "#fff"
        html += f'<tr style="background:{bg};">'
        for ci, cell in enumerate(row):
            if ci == highlight_idx:
                html += f'<td style="{hl_style}">{cell}</td>'
            else:
                html += f'<td style="{td_style}">{cell}</td>'
        html += "</tr>"

    if totals_row:
        # VICIdial's TOTALS row often collapses the leading identifier columns
        # (ID/CURRENT USER GROUP/MOST RECENT USER GRP) into nothing, so
        # totals_row can have fewer cells than header. Pad it with blanks
        # right after the label cell so every value lands under its correct
        # header column instead of drifting left.
        if header and len(totals_row) < len(header):
            pad = len(header) - len(totals_row)
            totals_row = [totals_row[0]] + [""] * pad + totals_row[1:]

        html += '<tr style="background:#e8f4f8;font-weight:bold;">'
        for ci, cell in enumerate(totals_row):
            if ci == highlight_idx:
                html += f'<td style="{hl_style}border-top:2px solid #1a1a2e;">{cell}</td>'
            else:
                html += f'<td style="{td_style}border-top:2px solid #1a1a2e;">{cell}</td>'
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


# ── SHARED SECTION PARSING ──────────────────────
# Split the raw outbound-stats text into its named sections. Used both to
# render the detailed tables and to build the plain-English executive summary,
# so both stay in sync with a single parsing pass.
SECTION_KEYS = [
    "TOTALS",
    "HUMAN ANSWERS",
    "DROPS",
    "NO ANSWERS",
    "CALL HANGUP REASON STATS",
    "CALL STATUS STATS",
    "LIST ID STATS",
    "CUSTOM STATUS CATEGORY STATS",
]

def split_into_sections(pre_text):
    sections = {k: [] for k in SECTION_KEYS}
    if not pre_text:
        return sections
    current = None
    for line in pre_text.split("\n"):
        stripped = line.strip()
        matched  = False
        for key in SECTION_KEYS:
            if key in stripped.upper():
                current = key
                matched = True
                break
        if current and not matched:
            sections[current].append(line)
    return sections


def parse_key_value_lines(lines):
    """Turn 'Label: value' lines (as seen in TOTALS/HUMAN ANSWERS/DROPS) into a dict."""
    kv = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("-"):
            continue
        if ":" in s:
            label, _, value = s.partition(":")
            label, value = label.strip(), value.strip()
            if label:
                kv[label] = value
    return kv


def find_value(kv, *keywords):
    """Case-insensitive substring lookup across a key/value dict's labels."""
    for keyword in keywords:
        for label, value in kv.items():
            if keyword.lower() in label.lower():
                return value
    return None


def outbound_text_to_html(pre_text):
    """Convert raw outbound calling stats text into readable HTML sections."""
    if not pre_text:
        return ("<p style='color:#92400e;background:#fffbeb;border:1px solid #fde68a;"
                "border-radius:6px;padding:10px 14px;font-size:13px;'>"
                "⚠️ Outbound stats couldn't be retrieved in time — the dialer was slow "
                "to respond for this date range. This does <strong>not</strong> mean no "
                "calls were made; it will be included once the dialer responds "
                "(try re-running the report, or check tomorrow's report).</p>")

    sections = split_into_sections(pre_text)

    def simple_section_html(sec):
        lines = [l for l in sections[sec] if l.strip() and not l.strip().startswith("-")]
        if not lines:
            return ""
        h = f'<h4 style="color:#2d3748;margin:20px 0 6px;font-size:13px;font-weight:600;">{sec}</h4>'
        h += '<table style="border-collapse:collapse;width:100%;max-width:560px;">'
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                label = parts[0].strip()
                value = parts[1].strip()
                h += (f'<tr>'
                      f'<td style="padding:5px 10px;color:#555;font-size:13px;width:72%;">{label}</td>'
                      f'<td style="padding:5px 10px;font-weight:bold;font-size:13px;">{value}</td>'
                      f'</tr>')
        h += "</table>"
        return h

    def pipe_table_html(sec, include_totals=True):
        lines = sections[sec]
        if not lines:
            return ""
        header    = None
        rows      = []
        total_row = None
        for line in lines:
            s = line.strip()
            if not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not any(cells):
                continue
            # Detect header: first pipe row where cells aren't all digits/empty
            if header is None:
                if not all(c.replace(" ", "").replace(":", "").replace(".", "").isdigit() or c == "" for c in cells):
                    header = cells
                continue
            if "TOTAL" in s.upper():
                total_row = cells
                continue
            if cells and cells[0]:
                rows.append(cells)

        if not header or not rows:
            return ""
        h  = f'<h4 style="color:#2d3748;margin:20px 0 6px;font-size:13px;font-weight:600;">{sec}</h4>'
        h += rows_to_html_table(header, rows, totals_row=total_row if include_totals else None)
        return h

    html = ""

    # ── Simple text sections ──
    html += simple_section_html("TOTALS")
    html += simple_section_html("HUMAN ANSWERS")
    html += simple_section_html("DROPS")

    # ── NO ANSWERS — show all lines including counts ──
    na_lines = [l for l in sections["NO ANSWERS"] if l.strip() and not l.strip().startswith("-")]
    if na_lines:
        html += '<h4 style="color:#2d3748;margin:20px 0 6px;font-size:13px;font-weight:600;">NO ANSWERS</h4>'
        html += '<table style="border-collapse:collapse;width:100%;max-width:560px;">'
        for line in na_lines:
            stripped = line.strip()
            # Lines like "Total NA calls -Busy,...:   6845  30.91%"
            if ":" in stripped:
                parts = stripped.split(":", 1)
                label = parts[0].strip()
                value = parts[1].strip()
                html += (f'<tr>'
                         f'<td style="padding:5px 10px;color:#555;font-size:13px;width:72%;">{label}</td>'
                         f'<td style="padding:5px 10px;font-weight:bold;font-size:13px;">{value}</td>'
                         f'</tr>')
        html += "</table>"

    # ── CALL HANGUP REASON STATS table ──
    html += pipe_table_html("CALL HANGUP REASON STATS", include_totals=True)

    # ── CALL STATUS STATS table ──
    html += pipe_table_html("CALL STATUS STATS", include_totals=True)

    # ── LIST ID STATS table — full table with all lists ──
    html += pipe_table_html("LIST ID STATS", include_totals=True)

    return html


# ── EXECUTIVE SUMMARY (plain-English recap for clients) ─────────
def build_executive_summary(campaign_name, start_date, cs_rows, pb_header, pb_totals, outbound_text, ytd_nonpause_hours=None):
    """A short, non-technical recap that sits above the detailed tables.
    Pulls a handful of headline numbers so clients get the gist without
    having to read the raw report."""
    sections  = split_into_sections(outbound_text) if outbound_text else {k: [] for k in SECTION_KEYS}
    totals_kv = parse_key_value_lines(sections.get("TOTALS", []))
    human_kv  = parse_key_value_lines(sections.get("HUMAN ANSWERS", []))
    drops_kv  = parse_key_value_lines(sections.get("DROPS", []))

    agent_count = len(cs_rows) if cs_rows else 0

    nonpause_total = None
    if pb_header and pb_totals:
        # Same right-alignment fix as rows_to_html_table: the TOTALS row
        # collapses the leading identifier columns into one label cell, so
        # its NONPAUSE value sits at (header_index - offset), not header_index.
        offset = len(pb_header) - len(pb_totals)
        for i, h in enumerate(pb_header):
            if "NONPAUSE" in h.upper():
                candidate = i - offset
                if 0 <= candidate < len(pb_totals):
                    nonpause_total = pb_totals[candidate]
                break

    total_calls   = find_value(totals_kv, "total calls", "calls dialed", "total dial")
    human_answers = find_value(human_kv, "human answers", "total human")
    total_drops   = find_value(drops_kv, "total drops", "drops")

    bullets = []

    agent_line = f"<strong>{agent_count}</strong> agent(s) worked this campaign"
    if nonpause_total:
        agent_line += f", logging <strong>{nonpause_total}</strong> of active talk/work time"
    bullets.append(agent_line + ".")

    if total_calls:
        bullets.append(f"The dialer placed <strong>{total_calls}</strong> total calls.")
    if human_answers:
        bullets.append(f"<strong>{human_answers}</strong> of those calls were answered by a live person.")
    if total_drops:
        bullets.append(f"<strong>{total_drops}</strong> calls were dropped before reaching an agent.")

    if not (total_calls or human_answers or total_drops):
        bullets.append("Detailed numbers are in the tables below — no summary metrics were found in yesterday's raw report.")

    if ytd_nonpause_hours is not None:
        ytd_start, ytd_end = get_ytd_dates()
        remaining = NONPAUSE_QUOTA_HOURS - ytd_nonpause_hours
        if remaining >= 0:
            quota_line = (
                f"Year-to-date ({ytd_start} – {ytd_end}): <strong>{ytd_nonpause_hours:.1f} hrs</strong> "
                f"of active NONPAUSE time logged against the <strong>{NONPAUSE_QUOTA_HOURS} hr</strong> target — "
                f"<strong>{remaining:.1f} hrs remaining</strong>."
            )
        else:
            quota_line = (
                f"Year-to-date ({ytd_start} – {ytd_end}): <strong>{ytd_nonpause_hours:.1f} hrs</strong> "
                f"of active NONPAUSE time logged, <strong>{abs(remaining):.1f} hrs over</strong> "
                f"the {NONPAUSE_QUOTA_HOURS} hr target."
            )
        bullets.append(quota_line)
    else:
        bullets.append(f"Year-to-date NONPAUSE total (vs. the {NONPAUSE_QUOTA_HOURS} hr target) couldn't be retrieved for this report.")

    bullet_html = "".join(f"<li style='margin-bottom:4px;'>{b}</li>" for b in bullets)

    return f"""
    <div style="background:#f0f7ff;border:1px solid #bee3f8;border-radius:8px;padding:16px 20px;margin-bottom:28px;">
      <h2 style="color:#2c5282;font-size:14px;font-weight:600;margin:0 0 8px;">📝 Summary — {campaign_name}, {start_date}</h2>
      <ul style="margin:0;padding-left:18px;color:#2d3748;font-size:13px;line-height:1.5;">
        {bullet_html}
      </ul>
    </div>
    """


def build_email_html(campaign_id, campaign_name, start_date, end_date, cs_data, pb_data, outbound_text, outbound_html, ytd_nonpause_hours=None):
    cs_header, cs_rows       = cs_data
    pb_header, pb_rows, pb_totals = pb_data

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    summary_html = build_executive_summary(campaign_name, start_date, cs_rows, pb_header, pb_totals, outbound_text, ytd_nonpause_hours)

    html = f"""
    <html><body style="font-family:'Helvetica Neue',Arial,sans-serif;background:#f7fafc;padding:24px;margin:0;color:#4a5568;">
    <div style="max-width:900px;margin:auto;">

      <!-- HEADER -->
      <div style="background:linear-gradient(135deg,#2d3748,#4a5568);padding:28px 32px;border-radius:12px 12px 0 0;">
        <h1 style="color:#f7fafc;margin:0;font-size:20px;font-weight:600;letter-spacing:0.3px;">📊 Daily Campaign Report — {campaign_name}</h1>
        <p style="color:#cbd5e0;margin:8px 0 0;font-size:13px;">
          Date: <strong style="color:#fff;">{start_date}</strong> &nbsp;|&nbsp;
          Generated: <span style="color:#e2e8f0;">{now}</span>
          <span style="color:#8f9bb3;font-size:11px;"> &nbsp;|&nbsp; Ref: {campaign_id}</span>
        </p>
      </div>

      <!-- BODY -->
      <div style="background:#fff;padding:28px 32px;border-radius:0 0 12px 12px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

        <!-- SUMMARY -->
        {summary_html}

        <!-- SECTION 1: CALL STATS -->
        <div style="margin-bottom:32px;">
          <h2 style="color:#2d3748;font-size:15px;font-weight:600;border-left:4px solid #63b3ed;padding-left:12px;margin-bottom:8px;">
            📞 Call Stats Breakdown
          </h2>
          <p style="color:#a0aec0;font-size:12px;margin:0 0 10px;">Statistics related to handling of calls only.</p>
          {rows_to_html_table(cs_header, cs_rows)}
        </div>

        <hr style="border:none;border-top:1px solid #edf2f7;margin:24px 0;">

        <!-- SECTION 2: PAUSE BREAKDOWN -->
        <div style="margin-bottom:32px;">
          <h2 style="color:#2d3748;font-size:15px;font-weight:600;border-left:4px solid #68d391;padding-left:12px;margin-bottom:8px;">
            ⏱️ Pause Code Breakdown
          </h2>
          <p style="color:#a0aec0;font-size:12px;margin:0 0 10px;">
            <span style="background:#fffbeb;color:#92400e;padding:2px 8px;border-radius:4px;font-weight:600;font-size:12px;">★ Highlighted = NONPAUSE (active working time)</span>
          </p>
          {rows_to_html_table(pb_header, pb_rows, highlight_col="NONPAUSE", totals_row=pb_totals)}
        </div>

        <hr style="border:none;border-top:1px solid #edf2f7;margin:24px 0;">

        <!-- SECTION 3: OUTBOUND CALLING STATS -->
        <div style="margin-bottom:16px;">
          <h2 style="color:#2d3748;font-size:15px;font-weight:600;border-left:4px solid #f6ad55;padding-left:12px;margin-bottom:8px;">
            📤 Outbound Calling Stats
          </h2>
          {outbound_html}
        </div>

      </div>

      <!-- FOOTER -->
      <p style="text-align:center;color:#a0aec0;font-size:11px;margin-top:16px;">
        Richie Rich Leads • Automated Daily Report • {now}
      </p>

    </div>
    </body></html>
    """
    return html


def send_email(to_emails, subject, html_body, cc_emails=None):
    if cc_emails is None:
        cc_emails = CC_EMAILS if not TEST_MODE else []

    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("   ❌ Gmail credentials missing — skipping email")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = ", ".join(to_emails)
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg.attach(MIMEText(html_body, "html"))

        all_recipients = to_emails + cc_emails

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.sendmail(GMAIL_USER, all_recipients, msg.as_string())

        cc_note = f" | CC: {', '.join(cc_emails)}" if cc_emails else " | CC: (none — TEST_MODE)"
        print(f"   ✅ Email sent to {', '.join(to_emails)}{cc_note}")
        return True
    except Exception as e:
        print(f"   ❌ Email error: {e}")
        return False


def send_daily_reports():
    start_date, end_date = get_report_dates()

    print("\n" + "="*55)
    print(f"📧 Daily Report Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Campaigns : {len(CAMPAIGN_EMAILS)}")
    if TEST_MODE:
        print(f"   ⚠️  TEST_MODE ON — all emails redirected to {TEST_RECIPIENT[0]}, CC suppressed")
    print("="*55)

    for campaign_id in CAMPAIGN_EMAILS:
        campaign_name = get_campaign_name(campaign_id)
        to_emails, cc_emails = resolve_recipients(campaign_id)
        print(f"\n   📋 {campaign_name} ({campaign_id}) → {', '.join(to_emails)}")

        # Fetch agent performance
        print(f"      Fetching agent performance...")
        ap_html = fetch_agent_performance(campaign_id, start_date, end_date)
        if not ap_html:
            print(f"      ⚠️  No agent performance data — skipping")
            time.sleep(8)
            continue

        (cs_header, cs_rows), (pb_header, pb_rows, pb_totals) = parse_agent_performance(ap_html)

        # Fetch outbound stats
        print(f"      Fetching outbound calling stats...")
        time.sleep(8)
        outbound_text = fetch_outbound_stats(campaign_id, start_date, end_date)
        outbound_html = outbound_text_to_html(outbound_text)

        # Fetch year-to-date NONPAUSE total (Jan 1 -> today) for the quota bullet
        print(f"      Fetching year-to-date NONPAUSE total...")
        time.sleep(8)
        ytd_nonpause_hours = fetch_ytd_nonpause_hours(campaign_id)

        # Build and send email
        subject   = f"📊 Daily Report — {campaign_name} — {start_date}"
        html_body = build_email_html(
            campaign_id, campaign_name, start_date, end_date,
            (cs_header, cs_rows),
            (pb_header, pb_rows, pb_totals),
            outbound_text, outbound_html,
            ytd_nonpause_hours
        )

        send_email(to_emails, subject, html_body, cc_emails=cc_emails)
        time.sleep(8)

    print(f"\n✅ All daily reports done.\n")


def run_scheduler():
    print("🤖 Daily Campaign Report Emailer Started!")
    print(f"   Campaigns : {len(CAMPAIGN_EMAILS)}")
    print(f"   Send time : {SEND_TIME} daily")
    if TEST_MODE:
        print(f"   ⚠️  TEST_MODE ON — all recipients redirected to {TEST_RECIPIENT[0]}\n")
    else:
        print(f"   Recipients: per-campaign mapping (see CAMPAIGN_EMAILS)\n")

    schedule.every().day.at(SEND_TIME).do(send_daily_reports)

    print(f"   ⏰ Next report scheduled at {SEND_TIME} daily. Waiting...\n")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""
Usage:
  python3 campaign_daily_report.py auto                                    → Run scheduler (sends at 08:00 daily)
  python3 campaign_daily_report.py now                                     → Send all reports RIGHT NOW
  python3 campaign_daily_report.py test RACILJRE                           → Send report for one campaign (yesterday's data)
  python3 campaign_daily_report.py testdate RACILJRE 2026-07-13 2026-07-14 → Send report for specific date range

Note: TEST_MODE is currently ON — every email (any command) goes to bipinvs014@gmail.com only, CC suppressed.
Set TEST_MODE = False near the top of the script to resume sending to real client addresses.
        """)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "auto":
        run_scheduler()

    elif cmd == "now":
        send_daily_reports()

    elif cmd == "test" and len(sys.argv) > 2:
        campaign_id   = sys.argv[2]
        campaign_name = get_campaign_name(campaign_id)
        # Use today as end date, yesterday as start
        start_date, end_date = get_report_dates()
        to_emails, cc_emails = resolve_recipients(campaign_id)

        print(f"\n🧪 Testing report for: {campaign_name} ({campaign_id})")
        print(f"   Date range: {start_date} to {end_date}")

        ap_html = fetch_agent_performance(campaign_id, start_date, end_date)
        if not ap_html:
            print("   ❌ No agent performance data")
            sys.exit(1)

        (cs_header, cs_rows), (pb_header, pb_rows, pb_totals) = parse_agent_performance(ap_html)
        time.sleep(8)
        outbound_text = fetch_outbound_stats(campaign_id, start_date, end_date)
        outbound_html = outbound_text_to_html(outbound_text)

        print(f"      Fetching year-to-date NONPAUSE total...")
        time.sleep(8)
        ytd_nonpause_hours = fetch_ytd_nonpause_hours(campaign_id)

        subject   = f"📊 Daily Report — {campaign_name} — {start_date}"
        html_body = build_email_html(
            campaign_id, campaign_name, start_date, end_date,
            (cs_header, cs_rows),
            (pb_header, pb_rows, pb_totals),
            outbound_text, outbound_html,
            ytd_nonpause_hours
        )

        print(f"   Sending to {', '.join(to_emails)}...")
        ok = send_email(to_emails, subject, html_body, cc_emails=cc_emails)
        if ok:
            print("   ✅ Check your inbox!")
        else:
            print("   ❌ Failed — check Gmail credentials in .env")

    elif cmd == "testdate" and len(sys.argv) > 4:
        # Usage: python3 campaign_daily_report.py testdate RACILJRE 2026-07-13 2026-07-14
        campaign_id   = sys.argv[2]
        campaign_name = get_campaign_name(campaign_id)
        start_date    = sys.argv[3]
        end_date      = sys.argv[4]
        to_emails, cc_emails = resolve_recipients(campaign_id)

        print(f"\n🧪 Testing report for: {campaign_name} ({campaign_id})")
        print(f"   Date range: {start_date} to {end_date}")

        ap_html = fetch_agent_performance(campaign_id, start_date, end_date)
        if not ap_html:
            print("   ❌ No agent performance data")
            sys.exit(1)

        (cs_header, cs_rows), (pb_header, pb_rows, pb_totals) = parse_agent_performance(ap_html)
        time.sleep(8)
        outbound_text = fetch_outbound_stats(campaign_id, start_date, end_date)
        outbound_html = outbound_text_to_html(outbound_text)

        print(f"      Fetching year-to-date NONPAUSE total...")
        time.sleep(8)
        ytd_nonpause_hours = fetch_ytd_nonpause_hours(campaign_id)

        subject   = f"📊 Daily Report — {campaign_name} — {start_date}"
        html_body = build_email_html(
            campaign_id, campaign_name, start_date, end_date,
            (cs_header, cs_rows),
            (pb_header, pb_rows, pb_totals),
            outbound_text, outbound_html,
            ytd_nonpause_hours
        )

        print(f"   Sending to {', '.join(to_emails)}...")
        ok = send_email(to_emails, subject, html_body, cc_emails=cc_emails)
        if ok:
            print("   ✅ Check your inbox!")
        else:
            print("   ❌ Failed — check Gmail credentials in .env")

    else:
        print(f"Unknown command: {cmd}")