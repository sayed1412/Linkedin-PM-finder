"""
LinkedIn "Hiring - Product Manager" Post Finder
------------------------------------------------
Searches Google's indexed LinkedIn posts (not LinkedIn directly - this stays
fully compliant with LinkedIn's Terms of Service) for organic "we're hiring"
style posts mentioning Product Manager roles, and appends new results to a
Google Sheet.

Designed to be run once per hour (e.g. via GitHub Actions cron).

Required environment variables:
    GOOGLE_API_KEY              - Google Cloud API key with Custom Search API enabled
    GOOGLE_CSE_ID               - Programmable Search Engine ID (cx)
    GOOGLE_SHEET_ID             - The ID of the target Google Sheet (from its URL)
    GOOGLE_SERVICE_ACCOUNT_FILE - Path to the service account JSON credentials file
"""

import os
import sys
import time
from datetime import datetime, timezone

import requests
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# Runs every 3 hours (8 runs/day), so up to 12 queries/run keeps total usage
# at 96/day - just under Google's 100 free queries/day. Add more only if
# you've enabled billing on the API.
KEYWORD_QUERIES = [
    'site:linkedin.com/posts "Product Manager" "we\'re hiring"',
    'site:linkedin.com/posts "Product Manager" "hiring" "apply"',
    'site:linkedin.com/posts "Senior Product Manager" "hiring"',
    'site:linkedin.com/posts "Product Manager" "join our team"',
    'site:linkedin.com/posts "Product Manager" "excited to announce" hiring',
    'site:linkedin.com/posts "Group Product Manager" hiring',
    'site:linkedin.com/posts "Product Manager" "open position"',
    'site:linkedin.com/posts "Product Manager" "we are looking for"',
    'site:linkedin.com/posts "Associate Product Manager" hiring',
    'site:linkedin.com/posts "Product Manager" remote hiring',
    'site:linkedin.com/posts "Principal Product Manager" hiring',
    'site:linkedin.com/posts "Product Manager" "apply now"',
]

SHEET_HEADER = ["Date Found (UTC)", "Search Term", "Post Title", "Post Link", "Snippet"]

# ---------------------------------------------------------------------------
# Google Custom Search
# ---------------------------------------------------------------------------

def google_search(query: str, num: int = 10):
    """Run one query against the Custom Search JSON API and return raw items."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": num}
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"  [warn] search failed ({resp.status_code}) for query: {query}")
        print(f"  [warn] response: {resp.text[:300]}")
        return []
    return resp.json().get("items", [])


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
    missing = [name for name in ["GOOGLE_API_KEY", "GOOGLE_CSE_ID", "GOOGLE_SHEET_ID"]
               if not os.environ.get(name)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    sheet = get_sheet()
    existing_rows = ensure_header(sheet)
    seen_links = load_seen_links(existing_rows)

    new_rows = []
    for query in KEYWORD_QUERIES:
        print(f"Searching: {query}")
        items = google_search(query)
        for item in items:
            link = item.get("link", "").strip()
            if "linkedin.com/posts" not in link:
                continue  # skip anything that isn't an individual post URL
            if link in seen_links:
                continue
            title = item.get("title", "")
            snippet = item.get("snippet", "").replace("\n", " ").strip()
            new_rows.append([
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                query,
                title,
                link,
                snippet,
            ])
            seen_links.add(link)
        time.sleep(1)  # be polite between calls

    if new_rows:
        sheet.append_rows(new_rows)
        print(f"Added {len(new_rows)} new post(s) to the sheet.")
    else:
        print("No new posts found this run.")


if __name__ == "__main__":
    main()
