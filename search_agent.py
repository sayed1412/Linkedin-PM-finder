"""
LinkedIn "Hiring - Product Manager" Post Finder
------------------------------------------------
Reads Google Alerts emails (delivered to a Gmail inbox you control) that
match "we're hiring / Product Manager" style LinkedIn posts, and appends
new results to a Google Sheet.

This replaces an earlier version that called Google's Custom Search JSON
API directly - that API is closed to new Google Cloud projects as of 2025
and is being shut down entirely on January 1, 2027, so it isn't usable for
a brand-new setup. Google Alerts + Gmail has no such restriction and is
free indefinitely.

Designed to be run every few hours (e.g. via GitHub Actions cron).

Required environment variables:
    GMAIL_ADDRESS               - The Gmail address receiving your Google Alerts
    GMAIL_APP_PASSWORD          - A 16-character Gmail App Password (not your normal password)
    GOOGLE_SHEET_ID             - The ID of the target Google Sheet (from its URL)
    GOOGLE_SERVICE_ACCOUNT_FILE - Path to the service account JSON credentials file
"""

import os
import sys
import imaplib
import email
from email.header import decode_header
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime, timezone

import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# Only process alert emails sent from Google's alerts system.
ALERT_SENDER = "googlealerts-noreply@google.com"

# Only keep links whose destination contains this - filters out Google's own
# navigation links (manage alerts, unsubscribe, etc.) inside the email.
TARGET_URL_FRAGMENT = "linkedin.com/posts"

SHEET_HEADER = ["Date Found (UTC)", "Alert Subject", "Post Title", "Post Link", "Email Date"]


# ---------------------------------------------------------------------------
# Gmail (IMAP)
# ---------------------------------------------------------------------------

def decode_mime_str(raw):
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            decoded += text.decode(enc or "utf-8", errors="ignore")
        else:
            decoded += text
    return decoded


def unwrap_google_link(href: str) -> str:
    """Google Alerts wraps every link like https://www.google.com/url?...&url=<real>&...
    Extract and URL-decode the real destination."""
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        for key in ("url", "q"):
            if key in qs and qs[key]:
                return unquote(qs[key][0])
    except Exception:
        pass
    return href


def extract_linkedin_links(html: str):
    """Return a list of (title, link) tuples for every LinkedIn post link found
    in a Google Alerts email body, picking the longest anchor text per unique link."""
    soup = BeautifulSoup(html, "html.parser")
    best_title_for_link = {}
    for a in soup.find_all("a", href=True):
        target = unwrap_google_link(a["href"])
        if TARGET_URL_FRAGMENT not in target:
            continue
        clean_link = target.split("?")[0]
        text = a.get_text(strip=True)
        if not text:
            continue
        if clean_link not in best_title_for_link or len(text) > len(best_title_for_link[clean_link]):
            best_title_for_link[clean_link] = text
    return [(title, link) for link, title in best_title_for_link.items()]


def fetch_new_alert_emails():
    """Connect to Gmail, find unread Google Alerts emails, and return their
    parsed subject/date/html body/uid - without marking them read yet."""
    results = []
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    # "All Mail" catches alerts even if a filter archived or labeled them.
    imap.select('"[Gmail]/All Mail"', readonly=False)

    status, data = imap.search(None, f'(UNSEEN FROM "{ALERT_SENDER}")')
    if status != "OK":
        print(f"  [warn] IMAP search failed: {status}")
        imap.logout()
        return results

    uids = data[0].split()
    print(f"Found {len(uids)} unread alert email(s).")

    for uid in uids:
        status, msg_data = imap.fetch(uid, "(BODY.PEEK[])")  # PEEK = don't mark as read yet
        if status != "OK" or not msg_data or msg_data[0] is None:
            continue
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject = decode_mime_str(msg.get("Subject", ""))
        date_hdr = msg.get("Date", "")

        html_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_body += payload.decode(charset, errors="ignore")
        else:
            if msg.get_content_type() == "text/html":
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    html_body = payload.decode(charset, errors="ignore")

        results.append({"uid": uid, "subject": subject, "date": date_hdr, "html": html_body})

    imap.logout()
    return results


def mark_emails_seen(uids):
    if not uids:
        return
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    imap.select('"[Gmail]/All Mail"', readonly=False)
    for uid in uids:
        imap.store(uid, "+FLAGS", "\\Seen")
    imap.logout()


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).sheet1


def ensure_header(sheet):
    values = sheet.get_all_values()
    if not values:
        sheet.append_row(SHEET_HEADER)
        return []
    return values


def load_seen_links(existing_rows):
    """Column D (index 3) holds the post link."""
    seen = set()
    for row in existing_rows[1:]:  # skip header
        if len(row) > 3 and row[3]:
            seen.add(row[3].strip())
    return seen


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    missing = [name for name in ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "GOOGLE_SHEET_ID"]
               if not os.environ.get(name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    sheet = get_sheet()
    existing_rows = ensure_header(sheet)
    seen_links = load_seen_links(existing_rows)

    emails = fetch_new_alert_emails()

    new_rows = []
    processed_uids = []
    for msg in emails:
        found_any = extract_linkedin_links(msg["html"])
        processed_uids.append(msg["uid"])
        for title, link in found_any:
            if link in seen_links:
                continue
            new_rows.append([
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                msg["subject"],
                title,
                link,
                msg["date"],
            ])
            seen_links.add(link)

    if new_rows:
        sheet.append_rows(new_rows)
        print(f"Added {len(new_rows)} new post(s) to the sheet.")
    else:
        print("No new posts found in this run's alert emails.")

    # Only mark emails as read after successfully processing them, so a
    # crash earlier in the run leaves them to retry next time.
    mark_emails_seen(processed_uids)


if __name__ == "__main__":
    main()
